import sqlite3

DATABASE = "automation_platform.db"

connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()

columns = {
    "schedule_enabled": "INTEGER DEFAULT 0",
    "schedule_type": "TEXT DEFAULT 'manual'",
    "schedule_value": "TEXT",
    "next_run": "DATETIME",
}

cursor.execute("PRAGMA table_info(jobs)")
existing_columns = [row[1] for row in cursor.fetchall()]

for column_name, column_type in columns.items():
    if column_name not in existing_columns:
        cursor.execute(
            f"""
            ALTER TABLE jobs
            ADD COLUMN {column_name} {column_type}
            """
        )
        print(f"Added column: {column_name}")
    else:
        print(f"Column already exists: {column_name}")

connection.commit()
connection.close()

print("\nDatabase migration completed successfully.")