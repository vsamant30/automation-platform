import os
import subprocess
import sys


CONFIG_COMMAND = [
    sys.executable,
    "-c",
    (
        "from app.core.config import settings; "
        "print(settings.SECRET_KEY)"
    ),
]


def run_config(
    *,
    environment: str,
    secret_key: str | None,
) -> subprocess.CompletedProcess[str]:
    process_environment = os.environ.copy()

    process_environment["ENVIRONMENT"] = environment

    if secret_key is None:
        process_environment.pop(
            "SECRET_KEY",
            None,
        )

    else:
        process_environment["SECRET_KEY"] = secret_key

    return subprocess.run(
        CONFIG_COMMAND,
        env=process_environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_requires_secret_key() -> None:
    result = run_config(
        environment="production",
        secret_key=None,
    )

    assert result.returncode != 0
    assert (
        "SECRET_KEY must be configured"
        in result.stderr
    )


def test_configured_secret_key_is_preserved() -> None:
    configured_secret = (
        "configured-security-test-secret"
    )

    result = run_config(
        environment="production",
        secret_key=configured_secret,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == configured_secret


def test_development_generates_temporary_secret() -> None:
    first_result = run_config(
        environment="development",
        secret_key=None,
    )

    second_result = run_config(
        environment="development",
        secret_key=None,
    )

    assert first_result.returncode == 0
    assert second_result.returncode == 0

    first_secret = first_result.stdout.strip()
    second_secret = second_result.stdout.strip()

    assert len(first_secret) >= 64
    assert len(second_secret) >= 64
    assert first_secret != second_secret

    assert (
        "temporary development key was generated"
        in first_result.stderr
    )