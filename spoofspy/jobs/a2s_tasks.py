import datetime
import logging
import socket
from typing import Any
from typing import Tuple
from typing import Union

import a2s
from a2s import BrokenMessageError
from a2s import BufferExhaustedError
from celery.utils.log import get_task_logger

from spoofspy import db
from spoofspy.jobs.app import app

# TODO: error handling.

A2S_TIMEOUT = 10.0

logger: logging.Logger = get_task_logger(__name__)

known_a2s_errors = (
    BrokenMessageError,
    BufferExhaustedError,
    socket.timeout,
    socket.gaierror,
    ConnectionRefusedError,
    OSError,
)


@app.task(ignore_result=True)
def a2s_info(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)
    info = {}

    try:
        info = a2s.info(addr, timeout=A2S_TIMEOUT)
    except known_a2s_errors as e:
        logger.error(
            "a2s_info error: %s %s %s: %s",
            addr, gameport, query_time, e
        )
    except Exception as e:
        logger.exception(
            "a2s_info exception: %s %s %s: %s",
            addr, gameport, query_time, e
        )

    info_fields = {
        key: value for
        key, value in info
    }

    with db.Session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_server_name=_pop(info_fields, "server_name"),
            a2s_map_name=_pop(info_fields, "map_name"),
            a2s_steam_id=_pop(info_fields, "steam_id"),
            a2s_player_count=_pop(info_fields, "player_count"),
            a2s_max_players=_pop(info_fields, "max_players"),
            a2s_info=info_fields,
        )
        sess.merge(state)


@app.task(ignore_result=True)
def a2s_rules(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)
    rules = {}

    try:
        rules = a2s.rules(addr, timeout=A2S_TIMEOUT)
    except known_a2s_errors as e:
        logger.error(
            "a2s_rules error: %s %s %s: %s",
            addr, gameport, query_time, e
        )
    except Exception as e:
        logger.exception(
            "a2s_rules exception: %s %s %s: %s",
            addr, gameport, query_time, e
        )

    num_open_pub = _pop(rules, "NumOpenPublicConnections")
    num_pub = _pop(rules, "NumPublicConnections")
    pi_count = _pop(rules, "PI_COUNT")

    with db.Session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_num_open_public_connections=num_open_pub,
            a2s_num_public_connections=num_pub,
            a2s_pi_count=pi_count,
            a2s_rules=rules,
        )
        sess.merge(state)


@app.task(ignore_result=True)
def a2s_players(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)
    players = []

    try:
        players = a2s.players(addr, timeout=A2S_TIMEOUT)
    except known_a2s_errors as e:
        logger.error(
            "a2s_players error: %s %s %s: %s",
            addr, gameport, query_time, e
        )
    except Exception as e:
        logger.exception(
            "a2s_players exception: %s %s %s: %s",
            addr, gameport, query_time, e
        )

    players = [
        {
            key: value
            for key, value in player
        } for player in players
    ]

    with db.Session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_players=players,
        )
        sess.merge(state)


def _coerce_tuple(x: Union[list, tuple]) -> Tuple:
    # Celery converts tuples to lists.
    return x[0], x[1]


def _pop(d: dict, key: Any, default: Any = None) -> Any:
    try:
        d.pop(key)
    except KeyError:
        return default
