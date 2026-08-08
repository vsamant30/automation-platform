import os

from app.services.secret_provider import (
    SecretProvider,
    SecretProviderError,
    validate_secret_name,
    validate_secret_value,
)


class AWSSecretsManagerProvider:
    """
    AWS Secrets Manager secret provider.

    Authentication is handled by boto3's
    standard credential provider chain.
    """

    def __init__(
        self,
        *,
        region_name: str = "",
    ):
        cleaned_region = region_name.strip()

        if not cleaned_region:
            cleaned_region = (
                os.getenv(
                    "AWS_REGION",
                    "",
                ).strip()
                or os.getenv(
                    "AWS_DEFAULT_REGION",
                    "",
                ).strip()
            )

        if not cleaned_region:
            raise ValueError(
                "AWS region is required."
            )

        self.region_name = cleaned_region

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
            import boto3

        except ImportError as error:
            raise SecretProviderError(
                "AWS Secrets Manager dependency "
                "is not installed."
            ) from error

        try:
            client = boto3.client(
                "secretsmanager",
                region_name=self.region_name,
            )

            response = client.get_secret_value(
                SecretId=cleaned_secret_name
            )

        except Exception as error:
            raise SecretProviderError(
                "AWS Secrets Manager secret "
                "retrieval failed for: "
                f"{cleaned_secret_name}"
            ) from error

        secret_value = response.get(
            "SecretString"
        )

        if secret_value is None:
            raise SecretProviderError(
                "AWS Secrets Manager returned "
                "no SecretString for: "
                f"{cleaned_secret_name}"
            )

        return validate_secret_value(
            secret_value,
            secret_name=cleaned_secret_name,
        )


def create_aws_secrets_manager_provider(
    *,
    region_name: str,
) -> SecretProvider:
    """
    Create an AWS Secrets Manager provider.
    """

    return AWSSecretsManagerProvider(
        region_name=region_name,
    )