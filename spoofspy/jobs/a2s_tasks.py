import datetime
import logging
import socket
from collections import defaultdict
from typing import Any
from typing import Dict
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

    resp = False
    try:
        info = a2s.info(addr, timeout=A2S_TIMEOUT)
        resp = True
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
            a2s_info_responded=resp,
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
    rules: Dict[str, str] = {}

    resp = False
    try:
        rules = a2s.rules(addr, timeout=A2S_TIMEOUT)
        resp = True
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

    # TODO: refactor this loop into functions etc.
    pi_objs = defaultdict(dict)
    to_del = set()
    ignore_idxs = set()
    for key, value in rules.items():
        if key.startswith("PI_"):
            try:
                idx = int(key.split("_")[-1])
                to_del.add(key)
            except ValueError:
                continue

            if idx in ignore_idxs:
                continue

            if key.startswith("PI_N_"):
                # Name.
                if value == "<<ChatLogger>>":
                    ignore_idxs.add(idx)
                    continue
                pi_objs[idx]["n"] = value
            elif key.startswith("PI_P_"):
                # Platform.
                pi_objs[idx]["p"] = value
            elif key.startswith("PI_S_"):
                # Score.
                pi_objs[idx]["s"] = value

    for key in to_del:
        del rules[key]

    with db.Session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_rules_responded=resp,
            a2s_num_open_public_connections=num_open_pub,
            a2s_num_public_connections=num_pub,
            a2s_pi_count=pi_count,
            a2s_pi_objects=pi_objs,
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

    resp = False
    try:
        players = a2s.players(addr, timeout=A2S_TIMEOUT)
        resp = True
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
            a2s_players_responded=resp,
            a2s_players=players,
        )
        sess.merge(state)


def _coerce_tuple(x: Union[list, tuple]) -> Tuple:
    # Celery converts tuples to lists.
    return x[0], x[1]


def _pop(d: dict, key: Any, default: Any = None) -> Any:
    try:
        return d.pop(key)
    except KeyError:
        return default
