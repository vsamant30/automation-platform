import os

from app.services.secret_provider import (
    SecretProvider,
    SecretProviderError,
    validate_secret_name,
    validate_secret_value,
)


class AzureKeyVaultProvider:
    """
    Azure Key Vault secret provider.

    Authentication order:
    1. Explicit service principal from environment
    2. DefaultAzureCredential fallback
    """

    def __init__(
        self,
        *,
        vault_url: str,
    ):
        cleaned_vault_url = (
            vault_url.strip().rstrip("/")
        )

        if not cleaned_vault_url:
            raise ValueError(
                "Azure Key Vault URL is required."
            )

        if not cleaned_vault_url.startswith(
            "https://"
        ):
            raise ValueError(
                "Azure Key Vault URL must start "
                "with https://."
            )

        self.vault_url = cleaned_vault_url

    def _build_credential(
        self,
    ):
        try:
            from azure.identity import (
                ClientSecretCredential,
                DefaultAzureCredential,
            )

        except ImportError as error:
            raise SecretProviderError(
                "Azure Identity dependency "
                "is not installed."
            ) from error

        tenant_id = os.getenv(
            "AZURE_TENANT_ID",
            "",
        ).strip()

        client_id = os.getenv(
            "AZURE_CLIENT_ID",
            "",
        ).strip()

        client_secret = os.getenv(
            "AZURE_CLIENT_SECRET",
            "",
        ).strip()

        configured_values = [
            bool(tenant_id),
            bool(client_id),
            bool(client_secret),
        ]

        if all(configured_values):
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )

        if any(configured_values):
            raise SecretProviderError(
                "Azure service principal "
                "configuration is incomplete."
            )

        return DefaultAzureCredential()

    def get_secret(
        self,
        secret_name: str,
    ) -> str:
        cleaned_secret_name = (
            validate_secret_name(
                secret_name
            )
        )

        try:
            from azure.keyvault.secrets import (
                SecretClient,
            )

        except ImportError as error:
            raise SecretProviderError(
                "Azure Key Vault dependency "
                "is not installed."
            ) from error

        credential = self._build_credential()

        try:
            client = SecretClient(
                vault_url=self.vault_url,
                credential=credential,
            )

            secret = client.get_secret(
                cleaned_secret_name
            )

        except Exception as error:
            raise SecretProviderError(
                "Azure Key Vault secret retrieval "
                "failed for: "
                f"{cleaned_secret_name}"
            ) from error

        return validate_secret_value(
            secret.value or "",
            secret_name=cleaned_secret_name,
        )


def create_azure_key_vault_provider(
    *,
    vault_url: str,
) -> SecretProvider:
    """
    Create an Azure Key Vault provider.
    """

    return AzureKeyVaultProvider(
        vault_url=vault_url,
    )