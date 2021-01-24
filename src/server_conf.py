from typing import Set, Optional, Tuple
from discord import Guild, TextChannel, Role

from database_connection import execute_query


class ServerConfiguration:
    def __init__(self, server: Guild):
        self.server = server
        self.server_id = server.id
        self.archive: Optional[TextChannel] = None
        self.queues: Set[TextChannel] = set()
        self.roles: Set[Role] = set()
        self.archive, self.queues, self.roles = self.request_server_conf()

    def request_server_conf(self) -> Tuple[Optional[TextChannel], Set[TextChannel], Set[Role]]:
        """
        Request the server configuration from the database
        @return: archive_id: Optional[int], queue_ids: List[int], role_ids: Set[int]
        """
        result = execute_query("SELECT archiveid, queues, roles FROM servers WHERE serverid = %s;",
                               (str(self.server_id),),
                               return_result=True)
        try:
            archive_id, queue_ids, role_ids = result[0]

            if archive_id is not None:  # Archive channel is set
                archive_id = int(archive_id)
                archive = self.server.get_channel(archive_id)
            else:
                archive = None
            if queue_ids is not None:  # At least one queue channel is set
                queue_ids = queue_ids.split()
                queue_ids = set(map(int, queue_ids))
                queues = set(map(self.server.get_channel, queue_ids))
            else:
                queues = set()
            if role_ids is not None:  # At least one role is designated queue manager
                role_ids = role_ids.split()
                role_ids = set(map(int, role_ids))
                roles = set(map(self.server.get_role, role_ids))
            else:
                roles = set()

            return archive, queues, roles
        except IndexError:  # Server has no configuration (no entry in database)
            return None, set(), set()

    def set_archive(self, archive: Optional[TextChannel]) -> None:
        self.archive = archive

    def set_queues(self, queues: Set[TextChannel]) -> None:
        self.queues = queues

    def set_roles(self, roles: Set[Role]) -> None:
        self.roles = roles
