from sqlalchemy import inspect, text

from app.db.database import engine


def add_category_column() -> None:
    inspector = inspect(engine)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("jobs")
    }

    if "category" in existing_columns:
        print("Category column already exists. No changes required.")
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE jobs
                ADD COLUMN category VARCHAR
                NOT NULL DEFAULT 'General'
                """
            )
        )

    print("Category column added successfully.")


if __name__ == "__main__":
    add_category_column()