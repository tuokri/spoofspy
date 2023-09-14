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
from celery import Task
from celery.utils.log import get_task_logger

from spoofspy import db
from spoofspy.jobs.app import app

A2S_TIMEOUT = 5.0

logger: logging.Logger = get_task_logger(__name__)

known_a2s_errors = (
    BrokenMessageError,
    BufferExhaustedError,
    socket.timeout,
    socket.gaierror,
    ConnectionRefusedError,
    OSError,
)


def _should_throw_retry(task: Task) -> bool:
    return task.request.retries > task.max_retries


def _log_timedelta(
        start: datetime.datetime,
        stop: datetime.datetime,
):
    logger.info(
        "parent query start to A2S query stop: %s seconds",
        (stop - start).total_seconds()
    )


@app.task(
    ignore_result=True,
    autoretry_for=(TimeoutError,),
    default_retry_delay=5,
    max_retries=3,
)
def a2s_info(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)
    info = {}

    resp = False
    resp_time = None
    try:
        info = a2s.info(addr, timeout=A2S_TIMEOUT)
        resp_time = datetime.datetime.now(tz=datetime.timezone.utc)
        resp = True
    except TimeoutError as e:
        # noinspection PyTypeChecker
        if _should_throw_retry(a2s_info):
            raise
        else:
            logger.info(
                "a2s_info error: %s %s %s: %s (max retries exceeded)",
                addr, gameport, query_time, e
            )
    except known_a2s_errors as e:
        logger.info(
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

    with app.db_session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_info_responded=resp,
            a2s_info_response_time=resp_time,
            a2s_server_name=_pop(info_fields, "server_name"),
            a2s_map_name=_pop(info_fields, "map_name"),
            a2s_steam_id=_pop(info_fields, "steam_id"),
            a2s_player_count=_pop(info_fields, "player_count"),
            a2s_max_players=_pop(info_fields, "max_players"),
            a2s_info=info_fields,
        )
        sess.merge(state)

    _log_timedelta(
        query_time,
        resp_time or datetime.datetime.now(tz=datetime.timezone.utc))


@app.task(
    ignore_result=True,
    autoretry_for=(TimeoutError,),
    default_retry_delay=5,
    max_retries=2,
)
def a2s_rules(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)
    rules: Dict[str, str] = {}

    resp = False
    resp_time = None
    try:
        rules = a2s.rules(addr, timeout=A2S_TIMEOUT)
        resp_time = datetime.datetime.now(tz=datetime.timezone.utc)
        resp = True
    except TimeoutError as e:
        # noinspection PyTypeChecker
        if _should_throw_retry(a2s_info):
            raise
        else:
            logger.info(
                "a2s_rules error: %s %s %s: %s (max retries exceeded)",
                addr, gameport, query_time, e
            )
    except known_a2s_errors as e:
        logger.info(
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
    pi_count = _pop(rules, "PI_COUNT", 0)
    mut_str = _pop(rules, "MutatorsRunning")
    mutators_running = []
    if mut_str:
        mut_str = mut_str.replace("(", "")
        mut_str = mut_str.replace(")", "")
        mut_str = mut_str.replace('"', "")
        mutators_running = mut_str.split(",")

    # TODO: refactor this loop into functions etc.
    pi_objs: dict[int, dict[str, str]] = defaultdict(dict)
    to_del = set()
    # ignore_idxs = set()
    for key, value in rules.items():
        if key.startswith("PI_"):
            try:
                # NOTE: index becomes a string in JSONB.
                idx = int(key.split("_")[-1])
                to_del.add(key)
            except ValueError:
                continue

            # if idx in ignore_idxs:
            #     continue

            if key.startswith("PI_N_"):
                # Name.
                # if value == "<<ChatLogger>>":
                #     ignore_idxs.add(idx)
                #     continue
                pi_objs[idx]["n"] = value
            elif key.startswith("PI_P_"):
                # Platform.
                pi_objs[idx]["p"] = value
            elif key.startswith("PI_S_"):
                # Score.
                pi_objs[idx]["s"] = value

    for key in to_del:
        del rules[key]

    with app.db_session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_rules_responded=resp,
            a2s_rules_response_time=resp_time,
            a2s_num_open_public_connections=num_open_pub,
            a2s_num_public_connections=num_pub,
            a2s_pi_count=pi_count,
            a2s_pi_objects=pi_objs,
            a2s_mutators_running=mutators_running,
            a2s_rules=rules,
        )
        sess.merge(state)

    _log_timedelta(
        query_time,
        resp_time or datetime.datetime.now(tz=datetime.timezone.utc))


@app.task(
    ignore_result=True,
    autoretry_for=(TimeoutError,),
    default_retry_delay=5,
    max_retries=2,
)
def a2s_players(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)
    players = []

    resp = False
    resp_time = None
    try:
        players = a2s.players(addr, timeout=A2S_TIMEOUT)
        resp = True
        resp_time = datetime.datetime.now(tz=datetime.timezone.utc)
    except TimeoutError as e:
        # noinspection PyTypeChecker
        if _should_throw_retry(a2s_info):
            raise
        else:
            logger.info(
                "a2s_players error: %s %s %s: %s (max retries exceeded)",
                addr, gameport, query_time, e
            )
    except known_a2s_errors as e:
        logger.info(
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

    with app.db_session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_players_responded=resp,
            a2s_players_response_time=resp_time,
            a2s_players=players,
        )
        sess.merge(state)

    _log_timedelta(
        query_time,
        resp_time or datetime.datetime.now(tz=datetime.timezone.utc))


def _coerce_tuple(x: Union[list, tuple]) -> Tuple:
    # Celery converts tuples to lists.
    return x[0], x[1]


def _pop(d: dict, key: Any, default: Any = None) -> Any:
    try:
        return d.pop(key)
    except KeyError:
        return default
