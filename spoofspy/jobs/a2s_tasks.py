import datetime
import ipaddress
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
from sqlalchemy import update
from sqlalchemy.exc import OperationalError

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
    autoretry_for=(TimeoutError, OperationalError),
    default_retry_delay=3,
    max_retries=3,
)
def a2s_info(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)  # type: ignore[assignment]
    info: a2s.SourceInfo | None = None

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

    if not info:
        logger.warning("no A2S info (%s) for %s", info, addr)
        return

    # TODO: keywords is optional, check its existence.
    # TODO: maybe don't use a2s exception here?
    if info and len(info.keywords) > 500:
        raise BufferExhaustedError("not processing info with keywords larger than 500 bytes")

    info_fields = {
        key: value for
        key, value in info
    }

    open_slots = None
    try:
        keywords = info_fields["keywords"]
        r_begin = keywords.find(",r")
        r_end = keywords.find(",b")
        try:
            open_slots = int(keywords[r_begin + 2:r_end])
        except Exception as e:
            logger.warning("error getting r value from '%s': %s",
                           keywords, e)
    except KeyError:
        pass

    ip_addr_obj = ipaddress.IPv4Address(addr[0])
    stmt = update(db.models.GameServerState).where(
        (db.models.GameServerState.time == query_time)
        & (db.models.GameServerState.game_server_address == ip_addr_obj)
        & (db.models.GameServerState.game_server_port == gameport)
    ).values(
        a2s_info_responded=resp,
        a2s_info_response_time=resp_time,
        a2s_server_name=_pop(info_fields, "server_name"),
        a2s_map_name=_pop(info_fields, "map_name"),
        a2s_steam_id=_pop(info_fields, "steam_id"),
        a2s_player_count=_pop(info_fields, "player_count"),
        a2s_max_players=_pop(info_fields, "max_players"),
        a2s_open_slots=open_slots,
        a2s_info=info_fields,
    )

    with app.db_session.begin() as sess:
        sess.execute(stmt)

    _log_timedelta(
        query_time,
        resp_time or datetime.datetime.now(tz=datetime.timezone.utc))


@app.task(
    ignore_result=True,
    autoretry_for=(TimeoutError, OperationalError),
    default_retry_delay=3,
    max_retries=3,
)
def a2s_rules(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)  # type: ignore[assignment]
    rules: Dict[str, str] = {}

    resp = False
    resp_time = None
    try:
        rules = a2s.rules(addr, timeout=A2S_TIMEOUT)
        if len(rules) > 750:
            raise BufferExhaustedError("not processing rules larger than 750 items")
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
    for key, value in rules.items():
        if key.startswith("PI_"):
            try:
                # NOTE: index becomes a string in JSONB.
                idx = int(key.split("_")[-1])
                to_del.add(key)
            except ValueError:
                continue

            if key.startswith("PI_N_"):
                pi_objs[idx]["n"] = value
            elif key.startswith("PI_P_"):
                # Platform.
                pi_objs[idx]["p"] = value
            elif key.startswith("PI_S_"):
                # Score.
                pi_objs[idx]["s"] = value

    for key in to_del:
        del rules[key]

    ip_addr_obj = ipaddress.IPv4Address(addr[0])
    stmt = update(db.models.GameServerState).where(
        (db.models.GameServerState.time == query_time)
        & (db.models.GameServerState.game_server_address == ip_addr_obj)
        & (db.models.GameServerState.game_server_port == gameport)
    ).values(
        a2s_rules_responded=resp,
        a2s_rules_response_time=resp_time,
        a2s_num_open_public_connections=num_open_pub,
        a2s_num_public_connections=num_pub,
        a2s_pi_count=pi_count,
        a2s_pi_objects=pi_objs,
        a2s_mutators_running=mutators_running,
        a2s_rules=rules,
    )

    with app.db_session.begin() as sess:
        sess.execute(stmt)

    _log_timedelta(
        query_time,
        resp_time or datetime.datetime.now(tz=datetime.timezone.utc))


@app.task(
    ignore_result=True,
    autoretry_for=(TimeoutError, OperationalError),
    default_retry_delay=3,
    max_retries=3,
)
def a2s_players(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)  # type: ignore[assignment]
    players = []

    resp = False
    resp_time = None
    try:
        players = a2s.players(addr, timeout=A2S_TIMEOUT)
        if len(players) > 255:
            raise BufferExhaustedError("not processing players larger than 255 items")
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

    ip_addr_obj = ipaddress.IPv4Address(addr[0])
    stmt = update(db.models.GameServerState).where(
        (db.models.GameServerState.time == query_time)
        & (db.models.GameServerState.game_server_address == ip_addr_obj)
        & (db.models.GameServerState.game_server_port == gameport)
    ).values(
        a2s_players_responded=resp,
        a2s_players_response_time=resp_time,
        a2s_players=players,
    )

    with app.db_session.begin() as sess:
        sess.execute(stmt)

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
