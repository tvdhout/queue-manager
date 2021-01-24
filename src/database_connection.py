from sys import stderr
from typing import Tuple
import mysql.connector


def execute_query(query: str, data: Tuple, return_result: bool = False, return_cursor_count: bool = False):
    try:  # Connect to database.
        connection = mysql.connector.connect(user='thijs', host='localhost', database='queuemanager')
        cursor = connection.cursor(buffered=True)
        cursor.execute(query, data)
        result = None
        if return_result:
            result = cursor.fetchall()
        elif return_cursor_count:
            result = cursor.rowcount
        connection.commit()  # Commit whatever happened in func to the database.
        cursor.close()
        connection.disconnect()
        return result
    except mysql.connector.Error:
        print("Database connection error", file=stderr)
        return
