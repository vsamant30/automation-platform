from sqlalchemy import inspect, text

from app.db.database import SessionLocal, engine
from app.db.models import ApplicationSettings


def create_application_settings_table() -> None:
    """
    Create the application_settings table when it
    does not already exist.
    """

    inspector = inspect(engine)

    if inspector.has_table("application_settings"):
        print(
            "application_settings table already exists."
        )
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE application_settings (
                    id INTEGER PRIMARY KEY,
                    email_notifications_enabled BOOLEAN
                        NOT NULL DEFAULT 0,
                    smtp_host VARCHAR,
                    smtp_port INTEGER
                        NOT NULL DEFAULT 587,
                    smtp_username VARCHAR,
                    smtp_password VARCHAR,
                    smtp_use_tls BOOLEAN
                        NOT NULL DEFAULT 1,
                    smtp_use_ssl BOOLEAN
                        NOT NULL DEFAULT 0,
                    email_from_address VARCHAR,
                    email_to_addresses TEXT,
                    notify_on_completed BOOLEAN
                        NOT NULL DEFAULT 1,
                    notify_on_failed BOOLEAN
                        NOT NULL DEFAULT 1,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )

    print(
        "application_settings table created successfully."
    )


def create_default_settings_row() -> None:
    """
    Ensure the singleton application settings row exists.
    """

    db = SessionLocal()

    try:
        existing_settings = (
            db.query(ApplicationSettings)
            .order_by(ApplicationSettings.id)
            .first()
        )

        if existing_settings:
            print(
                "Default application settings row "
                "already exists."
            )
            return

        default_settings = ApplicationSettings(
            email_notifications_enabled=False,
            smtp_host=None,
            smtp_port=587,
            smtp_username=None,
            smtp_password=None,
            smtp_use_tls=True,
            smtp_use_ssl=False,
            email_from_address=None,
            email_to_addresses=None,
            notify_on_completed=True,
            notify_on_failed=True,
        )

        db.add(default_settings)
        db.commit()
        db.refresh(default_settings)

        print(
            "Default application settings row created "
            f"successfully with ID {default_settings.id}."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def main() -> None:
    create_application_settings_table()
    create_default_settings_row()


if __name__ == "__main__":
    main()