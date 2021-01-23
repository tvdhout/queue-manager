from typing import List, Set, Optional, Tuple
import mysql.connector


class ServerConfiguration:
    def __init__(self, server_id: int, dbconnection: mysql.connector.MySQLConnection):
        self.server_id = server_id
        self.dbconnection = dbconnection
        self.archive_id, self.queue_ids, self.role_ids = self.request_server_conf()

    def request_server_conf(self) -> Tuple[Optional[int], List[int], Set[int]]:
        """
        Request the server configuration from the database
        @return: archive_id: Optional[int], queue_ids: List[int], role_ids: Set[int]
        """
        cursor = self.dbconnection.cursor()
        cursor.execute("SELECT archiveid, queues, roles FROM servers WHERE serverid = %s;",
                       (str(self.server_id),))
        try:
            archive_id, queues, roles = cursor.fetchall()[0]

            if archive_id is not None:  # Archive channel is set
                archive_id = int(archive_id)
            if queues is not None:  # At least one queue channel is set
                queues = queues.split()
                queues = list(map(int, queues))
            else:
                queues = []
            if roles is not None:  # At least one role is designated queue manager
                roles = roles.split()
                roles = set(map(int, roles))
            else:
                roles = set()

            return archive_id, queues, roles
        except IndexError:  # Server has no configuration (no entry in database)
            return None, [], set()

    def set_archive_id(self, archive_id: int):
        self.archive_id = archive_id

    def set_queue_ids(self, queue_ids: List[int]):
        self.queue_ids = queue_ids

    def set_role_ids(self, role_ids: Set[int]):
        self.role_ids = role_ids
