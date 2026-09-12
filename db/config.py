import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


def get_connection(use_database: bool = True):
    """
    Returns a new MySQL connection.
    use_database=False is used only when the database itself doesn't exist yet
    (e.g. during initial setup, before CREATE DATABASE has run).
    """
    try:
        config = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
        }
        if use_database:
            config["database"] = DB_NAME

        connection = mysql.connector.connect(**config)
        return connection

    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise