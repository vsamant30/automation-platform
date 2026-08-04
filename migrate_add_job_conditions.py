import sqlite3
from pathlib import Path


DATABASE_PATH = Path("automation_platform.db")


def column_exists(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    columns = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        column[1] == column_name
        for column in columns
    )


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database file not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        if not column_exists(
            connection,
            "jobs",
            "condition_type",
        ):
            connection.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN condition_type TEXT
                """
            )

            print(
                "Added condition_type column."
            )
        else:
            print(
                "Column condition_type already exists."
            )

        if not column_exists(
            connection,
            "jobs",
            "condition_value",
        ):
            connection.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN condition_value TEXT
                """
            )

            print(
                "Added condition_value column."
            )
        else:
            print(
                "Column condition_value already exists."
            )

        connection.commit()

        print(
            "Job condition migration completed successfully."
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()