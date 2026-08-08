from app.core.config import settings

from app.services.azure_key_vault_provider import (
    create_azure_key_vault_provider,
)

from app.services.secret_provider import (
    SecretProvider,
    SecretProviderError,
)


SUPPORTED_SECRET_PROVIDERS = {
    "local",
    "azure_key_vault",
}


def get_secret_provider() -> SecretProvider | None:
    """
    Return the configured external secret provider.

    local:
        No external provider is used.

    azure_key_vault:
        Azure Key Vault is used.
    """

    provider_name = (
        settings.SECRET_PROVIDER
        .strip()
        .lower()
    )

    if provider_name not in SUPPORTED_SECRET_PROVIDERS:
        raise SecretProviderError(
            "Unsupported secret provider: "
            f"{provider_name}"
        )

    if provider_name == "local":
        return None

    if provider_name == "azure_key_vault":
        if not settings.AZURE_KEY_VAULT_URL:
            raise SecretProviderError(
                "AZURE_KEY_VAULT_URL is required "
                "when SECRET_PROVIDER is "
                "azure_key_vault."
            )

        return create_azure_key_vault_provider(
            vault_url=(
                settings.AZURE_KEY_VAULT_URL
            ),
        )

    raise SecretProviderError(
        "Secret provider configuration "
        "could not be resolved."
    )