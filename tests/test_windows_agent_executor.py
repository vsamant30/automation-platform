from pathlib import Path

import pytest

import agents.windows_agent.executor as executor


def test_normal_python_executable_is_used(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    python_executable = tmp_path / "python.exe"

    monkeypatch.setattr(
        executor.sys,
        "executable",
        str(python_executable),
    )

    command = executor._build_command(
        "python",
        "automation.py",
    )

    assert command == [
        str(python_executable.resolve()),
        "automation.py",
    ]


def test_python_service_uses_sibling_python(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service_executable = (
        tmp_path / "pythonservice.exe"
    )

    python_executable = (
        tmp_path / "python.exe"
    )

    python_executable.touch()

    monkeypatch.setattr(
        executor.sys,
        "executable",
        str(service_executable),
    )

    command = executor._build_command(
        "python",
        "automation.py",
    )

    assert command == [
        str(python_executable.resolve()),
        "automation.py",
    ]


def test_missing_python_interpreter_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service_executable = (
        tmp_path / "pythonservice.exe"
    )

    monkeypatch.setattr(
        executor.sys,
        "executable",
        str(service_executable),
    )

    with pytest.raises(
        RuntimeError,
        match="usable Python interpreter",
    ):
        executor._build_command(
            "python",
            "automation.py",
        )