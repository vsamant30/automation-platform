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
        if column_exists(
            connection,
            "jobs",
            "dependency_job_id",
        ):
            print(
                "Column dependency_job_id already exists. "
                "No migration required."
            )
            return

        connection.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN dependency_job_id INTEGER
            REFERENCES jobs(id)
            """
        )

        connection.commit()

        print(
            "Migration completed successfully: "
            "dependency_job_id added to jobs table."
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()