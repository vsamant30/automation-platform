import os


class Settings:
    ENVIRONMENT = os.getenv(
        "ENVIRONMENT",
        "development",
    ).strip().lower()

    APP_NAME = os.getenv(
        "APP_NAME",
        "Automation Platform API",
    )

    APP_VERSION = os.getenv(
        "APP_VERSION",
        "2.0.0",
    )

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "",
    ).strip()

    if not SECRET_KEY:
        if ENVIRONMENT == "production":
            raise RuntimeError(
                "SECRET_KEY must be configured "
                "when ENVIRONMENT=production."
            )

        SECRET_KEY = (
            "change-this-secret-key-before-production"
        )

    JWT_ALGORITHM = os.getenv(
        "JWT_ALGORITHM",
        "HS256",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "60",
        )
    )

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///automation_platform.db",
    )

    SECRET_PROVIDER = os.getenv(
        "SECRET_PROVIDER",
        "local",
    ).strip().lower()

    AZURE_KEY_VAULT_URL = os.getenv(
        "AZURE_KEY_VAULT_URL",
        "",
    ).strip().rstrip("/")

    AWS_REGION = (
        os.getenv(
            "AWS_REGION",
            "",
        ).strip()
        or os.getenv(
            "AWS_DEFAULT_REGION",
            "",
        ).strip()
    )

    VAULT_ADDR = os.getenv(
        "VAULT_ADDR",
        "",
    ).strip().rstrip("/")

    VAULT_NAMESPACE = os.getenv(
        "VAULT_NAMESPACE",
        "",
    ).strip()

    VAULT_MOUNT_POINT = os.getenv(
        "VAULT_MOUNT_POINT",
        "secret",
    ).strip().strip("/")

    EMAIL_NOTIFICATIONS_ENABLED = (
        os.getenv(
            "EMAIL_NOTIFICATIONS_ENABLED",
            "false",
        ).strip().lower()
        == "true"
    )

    SMTP_HOST = os.getenv(
        "SMTP_HOST",
        "",
    )

    SMTP_PORT = int(
        os.getenv(
            "SMTP_PORT",
            "587",
        )
    )

    SMTP_USERNAME = os.getenv(
        "SMTP_USERNAME",
        "",
    )

    SMTP_PASSWORD = os.getenv(
        "SMTP_PASSWORD",
        "",
    )

    SMTP_USE_TLS = (
        os.getenv(
            "SMTP_USE_TLS",
            "true",
        ).strip().lower()
        == "true"
    )

    SMTP_USE_SSL = (
        os.getenv(
            "SMTP_USE_SSL",
            "false",
        ).strip().lower()
        == "true"
    )

    EMAIL_FROM_ADDRESS = os.getenv(
        "EMAIL_FROM_ADDRESS",
        "",
    )

    EMAIL_TO_ADDRESSES = os.getenv(
        "EMAIL_TO_ADDRESSES",
        "",
    )

    EMAIL_NOTIFY_ON_COMPLETED = (
        os.getenv(
            "EMAIL_NOTIFY_ON_COMPLETED",
            "true",
        ).strip().lower()
        == "true"
    )

    EMAIL_NOTIFY_ON_FAILED = (
        os.getenv(
            "EMAIL_NOTIFY_ON_FAILED",
            "true",
        ).strip().lower()
        == "true"
    )


settings = Settings()