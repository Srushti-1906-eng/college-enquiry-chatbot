import mysql.connector
from config import DB_CONFIG


def get_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"]
        )

        return connection

    except mysql.connector.Error as err:
        print("Database Connection Error:", err)
        return None