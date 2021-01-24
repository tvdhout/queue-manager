from sys import stderr
from typing import Tuple, Optional, Union
import mysql.connector


def execute_query(query: str, data: Optional[Tuple] = None, return_result: bool = False,
                  return_cursor_count: bool = False) -> Union[None, list, int]:
    """
    Execute the given query on the database.
    @param query: str: The query to execute
    @param data: Optional[Tuple] the data to include in the query
    @param return_result: bool: Whether or not to return the results from the query
    @param return_cursor_count: Whether or not to return the number of rows affected in the database
    @return: None, list or int
    """
    try:  # Connect to database.
        connection = mysql.connector.connect(user='thijs', host='localhost', database='queuemanager')
        cursor = connection.cursor(buffered=True)
        if data is not None:
            cursor.execute(query, data)
        else:
            cursor.execute(query)
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
