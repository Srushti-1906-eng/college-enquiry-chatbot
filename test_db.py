from database import get_connection


connection = get_connection()

if connection:
    print("Database connected successfully!")
    connection.close()
else:
    print("Database connection failed!")