# TODO: is this layer necessary?

from typing import Tuple

import a2s
from a2s.defaults import DEFAULT_TIMEOUT


def server_info(
        addr: Tuple[str, int],
        timeout: float = DEFAULT_TIMEOUT,
):
    info = a2s.info(addr, timeout=timeout)


def server_rules(
        addr: Tuple[str, int],
        timeout: float = DEFAULT_TIMEOUT,
):
    rules = a2s.rules(addr, timeout=timeout)


def server_players(
        addr: Tuple[str, int],
        timeout: float = DEFAULT_TIMEOUT,
):
    players = a2s.players(addr, timeout=timeout)
