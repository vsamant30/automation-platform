import os

from app.services.secret_provider import (
    SecretProvider,
    SecretProviderError,
    validate_secret_name,
    validate_secret_value,
)


class HashiCorpVaultProvider:
    """
    HashiCorp Vault KV v2 secret provider.

    Authentication uses the standard
    VAULT_TOKEN environment variable.
    """

    def __init__(
        self,
        *,
        vault_addr: str = "",
        namespace: str = "",
        mount_point: str = "secret",
    ):
        cleaned_vault_addr = (
            vault_addr.strip()
            or os.getenv(
                "VAULT_ADDR",
                "",
            ).strip()
        )

        if not cleaned_vault_addr:
            raise ValueError(
                "HashiCorp Vault address is required."
            )

        if not cleaned_vault_addr.startswith(
            ("http://", "https://")
        ):
            raise ValueError(
                "HashiCorp Vault address must start "
                "with http:// or https://."
            )

        cleaned_namespace = (
            namespace.strip()
            or os.getenv(
                "VAULT_NAMESPACE",
                "",
            ).strip()
        )

        cleaned_mount_point = (
            mount_point.strip().strip("/")
        )

        if not cleaned_mount_point:
            raise ValueError(
                "HashiCorp Vault mount point is required."
            )

        self.vault_addr = (
            cleaned_vault_addr.rstrip("/")
        )
        self.namespace = cleaned_namespace
        self.mount_point = cleaned_mount_point

    def get_secret(
        self,
        secret_name: str,
    ) -> str:
        cleaned_secret_name = (
            validate_secret_name(
                secret_name
            )
        )

        token = os.getenv(
            "VAULT_TOKEN",
            "",
        ).strip()

        if not token:
            raise SecretProviderError(
                "VAULT_TOKEN is not configured."
            )

        try:
            import hvac

        except ImportError as error:
            raise SecretProviderError(
                "HashiCorp Vault dependency "
                "is not installed."
            ) from error

        try:
            client = hvac.Client(
                url=self.vault_addr,
                token=token,
                namespace=(
                    self.namespace
                    or None
                ),
            )

            response = (
                client.secrets.kv.v2.read_secret_version(
                    path=cleaned_secret_name,
                    mount_point=self.mount_point,
                )
            )

        except Exception as error:
            raise SecretProviderError(
                "HashiCorp Vault secret retrieval "
                "failed for: "
                f"{cleaned_secret_name}"
            ) from error

        data = (
            response.get("data", {})
            .get("data", {})
        )

        secret_value = data.get(
            "value"
        )

        if secret_value is None:
            raise SecretProviderError(
                "HashiCorp Vault secret response "
                "does not contain key 'value' for: "
                f"{cleaned_secret_name}"
            )

        return validate_secret_value(
            secret_value,
            secret_name=cleaned_secret_name,
        )


def create_hashicorp_vault_provider(
    *,
    vault_addr: str,
    namespace: str = "",
    mount_point: str = "secret",
) -> SecretProvider:
    """
    Create a HashiCorp Vault provider.
    """

    return HashiCorpVaultProvider(
        vault_addr=vault_addr,
        namespace=namespace,
        mount_point=mount_point,
    )