# TODO: is this layer necessary?
from typing import List
from typing import Tuple

import a2s
from a2s.defaults import DEFAULT_TIMEOUT


# TODO: don't handle errors here and instead handle
#   them in the Celery tasks?

def server_info(
        addr: Tuple[str, int],
        timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    try:
        info = a2s.info(addr, timeout=timeout)
    except TimeoutError:
        return {}

    return {
        name: value
        for name, value in info
    }


def server_rules(
        addr: Tuple[str, int],
        timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    try:
        rules = a2s.rules(addr, timeout=timeout)
        return rules
    except TimeoutError:
        return {}


def server_players(
        addr: Tuple[str, int],
        timeout: float = DEFAULT_TIMEOUT,
) -> List[dict]:
    try:
        players = a2s.players(addr, timeout=timeout)
    except TimeoutError:
        return []

    return [
        {
            name: value
            for name, value in player
        }
        for player in players
    ]
