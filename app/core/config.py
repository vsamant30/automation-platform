import os


class Settings:
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
        "change-this-secret-key-before-production",
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


settings = Settings()