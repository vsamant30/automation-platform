from app.core.config import settings

from app.services.aws_secrets_manager_provider import (
    create_aws_secrets_manager_provider,
)

from app.services.azure_key_vault_provider import (
    create_azure_key_vault_provider,
)

from app.services.hashicorp_vault_provider import (
    create_hashicorp_vault_provider,
)

from app.services.secret_provider import (
    SecretProvider,
    SecretProviderError,
)


SUPPORTED_SECRET_PROVIDERS = {
    "local",
    "azure_key_vault",
    "aws_secrets_manager",
    "hashicorp_vault",
}


def get_secret_provider() -> SecretProvider | None:
    """
    Return the configured external secret provider.

    local:
        No external provider is used.

    azure_key_vault:
        Azure Key Vault is used.

    aws_secrets_manager:
        AWS Secrets Manager is used.

    hashicorp_vault:
        HashiCorp Vault KV v2 is used.
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

    if provider_name == "aws_secrets_manager":
        if not settings.AWS_REGION:
            raise SecretProviderError(
                "AWS_REGION or AWS_DEFAULT_REGION "
                "is required when SECRET_PROVIDER "
                "is aws_secrets_manager."
            )

        return create_aws_secrets_manager_provider(
            region_name=settings.AWS_REGION,
        )

    if provider_name == "hashicorp_vault":
        if not settings.VAULT_ADDR:
            raise SecretProviderError(
                "VAULT_ADDR is required when "
                "SECRET_PROVIDER is "
                "hashicorp_vault."
            )

        if not settings.VAULT_MOUNT_POINT:
            raise SecretProviderError(
                "VAULT_MOUNT_POINT is required "
                "when SECRET_PROVIDER is "
                "hashicorp_vault."
            )

        return create_hashicorp_vault_provider(
            vault_addr=settings.VAULT_ADDR,
            namespace=settings.VAULT_NAMESPACE,
            mount_point=settings.VAULT_MOUNT_POINT,
        )

    raise SecretProviderError(
        "Secret provider configuration "
        "could not be resolved."
    )