from typing import Protocol


class SecretProviderError(RuntimeError):
    """
    Raised when a configured secret provider
    cannot retrieve a requested secret.
    """


class SecretProvider(Protocol):
    """
    Common contract implemented by external
    secret-management providers.
    """

    def get_secret(
        self,
        secret_name: str,
    ) -> str:
        """
        Return one secret value by name.
        """

        ...


def validate_secret_name(
    secret_name: str,
) -> str:
    """
    Normalize and validate a secret name.
    """

    cleaned_name = secret_name.strip()

    if not cleaned_name:
        raise ValueError(
            "Secret name is required."
        )

    return cleaned_name

def validate_secret_value(
    secret_value: str,
    *,
    secret_name: str,
) -> str:
    """
    Validate a secret value returned by a
    provider without modifying or exposing it.
    """

    if not secret_value:
        raise SecretProviderError(
            "Secret provider returned an empty "
            f"value for: {secret_name}"
        )

    return secret_value