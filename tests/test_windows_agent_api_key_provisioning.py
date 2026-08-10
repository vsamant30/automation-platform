from pathlib import Path

import pytest

from agents.windows_agent import (
    provision_api_key,
)


def test_matching_api_key_is_saved_and_verified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    api_key = "test-agent-api-key"
    prompts = iter(
        [
            api_key,
            api_key,
        ]
    )

    secret_file = (
        tmp_path
        / "agent_api_key.bin"
    )

    saved_values: list[str] = []

    monkeypatch.setattr(
        provision_api_key,
        "getpass",
        lambda prompt: next(prompts),
    )

    def fake_save_agent_api_key(
        value: str,
    ) -> Path:
        saved_values.append(value)
        return secret_file

    monkeypatch.setattr(
        provision_api_key,
        "save_agent_api_key",
        fake_save_agent_api_key,
    )

    monkeypatch.setattr(
        provision_api_key,
        "load_agent_api_key",
        lambda path: api_key,
    )

    provision_api_key.provision_agent_api_key()

    assert saved_values == [api_key]


def test_empty_api_key_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = iter(
        [
            "",
            "",
        ]
    )

    monkeypatch.setattr(
        provision_api_key,
        "getpass",
        lambda prompt: next(prompts),
    )

    with pytest.raises(
        ValueError,
        match="Agent API key is required",
    ):
        provision_api_key.provision_agent_api_key()


def test_mismatched_confirmation_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = iter(
        [
            "first-api-key",
            "different-api-key",
        ]
    )

    monkeypatch.setattr(
        provision_api_key,
        "getpass",
        lambda prompt: next(prompts),
    )

    with pytest.raises(
        ValueError,
        match="confirmation does not match",
    ):
        provision_api_key.provision_agent_api_key()


def test_failed_storage_verification_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    api_key = "expected-api-key"
    prompts = iter(
        [
            api_key,
            api_key,
        ]
    )

    secret_file = (
        tmp_path
        / "agent_api_key.bin"
    )

    monkeypatch.setattr(
        provision_api_key,
        "getpass",
        lambda prompt: next(prompts),
    )

    monkeypatch.setattr(
        provision_api_key,
        "save_agent_api_key",
        lambda value: secret_file,
    )

    monkeypatch.setattr(
        provision_api_key,
        "load_agent_api_key",
        lambda path: "wrong-api-key",
    )

    with pytest.raises(
        RuntimeError,
        match="verification failed",
    ):
        provision_api_key.provision_agent_api_key()