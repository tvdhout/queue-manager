from typing import Tuple

TOKEN = open('/etc/QueueManagerToken', 'r').read()  # Bot token issued by Discord
PREFIX = '?'

DEV_TOKEN = open('/etc/QueueManagerDevToken', 'r').read()
DEV_PREFIX = '$'


def config(release: bool) -> Tuple[str, str]:
    if release:
        return TOKEN, PREFIX
    return DEV_TOKEN, DEV_PREFIX
