import os
import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "students.db"


def get_database_path() -> Path:
    return Path(os.environ.get("STUDENTS_DB_PATH", DEFAULT_DATABASE_PATH))


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                date_of_birth TEXT NOT NULL,
                email TEXT COLLATE NOCASE UNIQUE,
                phone TEXT,
                course TEXT,
                address TEXT,
                enrollment_date TEXT,
                CHECK (
                    (email IS NOT NULL AND length(trim(email)) > 0)
                    OR (phone IS NOT NULL AND length(trim(phone)) > 0)
                )
            )
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)
