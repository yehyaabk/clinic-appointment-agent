import os
from config import get_connection, DB_NAME

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def create_database_if_not_exists():
    """Connects without selecting a database, and creates it if missing."""
    connection = get_connection(use_database=False)
    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    print(f"Database '{DB_NAME}' is ready.")
    cursor.close()
    connection.close()


def run_schema():
    connection = get_connection(use_database=True)
    cursor = connection.cursor()

    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()

    for statement in schema_sql.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)

    connection.commit()
    print("Schema applied successfully.")
    cursor.close()
    connection.close()


if __name__ == "__main__":
    create_database_if_not_exists()
    run_schema()