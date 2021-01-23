from typing import List, Set, Optional, Tuple
import mysql.connector


class ServerConf:
    def __init__(self, server_id: int, dbconnection: mysql.connector.MySQLConnection):
        self.server_id = server_id
        self.dbconnection = dbconnection
        self.archive_id, self.queue_ids, self.role_ids = self.request_server_conf()

    def request_server_conf(self) -> Tuple[Optional[int], List[int], Set[int]]:
        cursor = self.dbconnection.cursor()
        cursor.execute("SELECT archiveid, queues, roles FROM servers WHERE serverid = %s;",
                       (str(self.server_id),))
        try:
            archive_id, queues, roles = cursor.fetchall()[0]

            if archive_id is not None:
                archive_id = int(archive_id)
            if queues is not None:
                queues = queues.split()
                queues = list(map(int, queues))
            else:
                queues = []
            if roles is not None:
                roles = roles.split()
                roles = set(map(int, roles))
            else:
                roles = set()

            return archive_id, queues, roles
        except IndexError:  # server has no configuration
            return None, [], set()
