from typing import Tuple

import a2s


def server_info(addr: Tuple[str, int]):
    a2s.info(addr)


def server_rules(addr: Tuple[str, int]):
    a2s.rules(addr)


def server_players():
    pass
