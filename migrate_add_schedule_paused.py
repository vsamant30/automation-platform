import sqlite3
from pathlib import Path


DATABASE_PATH = Path("automation_platform.db")


def column_exists(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    cursor = connection.execute(
        f"PRAGMA table_info({table_name})"
    )

    return any(
        row[1] == column_name
        for row in cursor.fetchall()
    )


def migrate() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database file was not found: "
            f"{DATABASE_PATH.resolve()}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        if column_exists(
            connection,
            "jobs",
            "schedule_paused",
        ):
            print(
                "Column jobs.schedule_paused already exists. "
                "No migration was required."
            )
            return

        connection.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN schedule_paused BOOLEAN
            NOT NULL DEFAULT 0
            """
        )

        connection.commit()

        print(
            "Migration completed successfully: "
            "jobs.schedule_paused was added."
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    migrate()