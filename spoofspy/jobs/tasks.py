import dataclasses
import datetime
import ipaddress
import logging
import os
import random
from typing import Any
from typing import Dict
from typing import Optional

import icmplib
import redis
import redis.lock
import sqlalchemy
from celery import Celery
from celery.signals import beat_init
from celery.utils.log import get_logger
from celery.utils.log import get_task_logger
from sqlalchemy import bindparam
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import load_only

from spoofspy import coding
from spoofspy import db
from spoofspy.heuristics import trust
from spoofspy.jobs import a2s_tasks
from spoofspy.jobs.app import app
from spoofspy.utils.deployment import is_prod_deployment
from spoofspy.web import GameServerResult
from spoofspy.web import SteamWebAPI

DISCOVER_DELAY_MIN = 0.0
DISCOVER_DELAY_MAX = 10.0

TRUST_KEY = "_spoofspy_trust"
TRUST_LOCK_KEY = "_spoofspy_trust_lock"

_webapi: Optional[SteamWebAPI] = None

logger: logging.Logger = get_task_logger(__name__)
beat_logger: logging.Logger = get_logger(f"beat.{__name__}")

_redis_client: Optional[redis.Redis] = None


# TODO: use upserts instead of merging in a loop!
# https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-queryguide-upsert

def webapi() -> SteamWebAPI:
    global _webapi
    if _webapi is None:
        _webapi = SteamWebAPI(key=os.environ["STEAM_WEB_API_KEY"])
        logger.info("created SteamWebAPI instance: %s", _webapi)
    return _webapi


def redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        pool = redis.BlockingConnectionPool.from_url(
            os.environ["REDIS_URL"],
            max_connections=5,
            timeout=30,
        )
        _redis_client = redis.Redis(
            connection_pool=pool,
        )
    return _redis_client


if is_prod_deployment():
    QUERY_INTERVAL = EVAL_INTERVAL = 5 * 60
else:
    QUERY_INTERVAL = EVAL_INTERVAL = 1 * 60

A2S_TASK_EXPIRY = QUERY_INTERVAL * 2


@beat_init.connect
def on_beat_init(*_args, **_kwargs):
    beat_logger.info("using QUERY_INTERVAL=%s", QUERY_INTERVAL)
    beat_logger.info("using EVAL_INTERVAL=%s", EVAL_INTERVAL)


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **_kwargs):
    sender.add_periodic_task(
        QUERY_INTERVAL,
        query_servers.s(),
        expires=QUERY_INTERVAL,
    )

    sender.add_periodic_task(
        EVAL_INTERVAL,
        eval_server_trust_scores.s(
            timedelta={"seconds": EVAL_INTERVAL * 2},
        ),
        expires=EVAL_INTERVAL + 60,
    )

    delta_24h = datetime.timedelta(hours=24)
    sender.add_periodic_task(
        delta_24h,
        eval_server_trust_scores.s(
            timedelta={"hours": 24},
        ),
        expires=(delta_24h * 2).total_seconds(),
    )

    sender.add_periodic_task(
        QUERY_INTERVAL,
        cache_trust_aggregate.s(),
        expires=QUERY_INTERVAL,
    )

    # Re-check ALL null trust_scores.
    # TODO: probably only needed during active development
    #   because trust eval algo is still evolving?
    # sender.add_periodic_task(
    #     crontab(
    #         hour="14",
    #         minute="02",
    #     ),
    #     eval_server_trust_scores.s(
    #         timedelta=None,
    #     ),
    #     expires=600,
    # )

    # Re-check ALL null a2s_mutators_running.
    # TODO: probably only needed during active development
    #   because trust eval algo is still evolving?
    # sender.add_periodic_task(
    #     crontab(
    #         hour="13",
    #         minute="27",
    #     ),
    #     check_muts_running.s(),
    #     expires=600,
    # )


# TODO: dev only task.
# @app.task(ignore_result=True)
# def check_muts_running():
#     stmt = select(db.models.GameServerState).where(
#         (db.models.GameServerState.a2s_mutators_running.is_(None))
#         & (db.models.GameServerState.a2s_rules_responded.is_not(None))
#     ).options(
#         load_only(
#             db.models.GameServerState.a2s_mutators_running,
#             db.models.GameServerState.a2s_rules_responded,
#         )
#     ).execution_options(yield_per=1000)
#
#     x = 0
#     with app.db_session.begin() as sess:
#         states = sess.scalars(stmt)
#         for state in states:
#             try:
#                 mut_str = state.a2s_rules.pop("MutatorsRunning")
#             except KeyError as e:
#                 mut_str = ""
#                 logger.warning("error: %s", e)
#
#             mutators_running = []
#             if mut_str:
#                 mut_str = mut_str.replace("(", "")
#                 mut_str = mut_str.replace(")", "")
#                 mut_str = mut_str.replace('"', "")
#                 mutators_running = mut_str.split(",")
#
#             x += 1
#             logger.info("%s %s:%s: muts running: %s",
#                         x,
#                         state.game_server_address,
#                         state.game_server_port,
#                         mutators_running,
#                         )
#             state.a2s_mutators_running = mutators_running
#
#         sess.merge(state)


@app.task(ignore_result=True)
def eval_server_trust_scores(
        timedelta: dict[str, int] | None,
):
    # # # Celery doesn't have an official way of adding jitter
    # # # to periodic tasks, so we simulate that here by sleeping.
    # slp = random.uniform(0.0, 25.0)
    # logger.info("sleeping %s seconds before doing work", slp)
    # time.sleep(slp)

    wheres = [
        (db.models.GameServerState.trust_score.is_(None))
        & (db.models.GameServerState.a2s_info_responded.is_not(None))
        & (db.models.GameServerState.a2s_rules_responded.is_not(None))
        & (db.models.GameServerState.a2s_players_responded.is_not(None))
    ]

    if timedelta:
        min_dt = datetime.datetime.now(tz=datetime.timezone.utc)
        min_dt -= datetime.timedelta(**timedelta)
        wheres.append(
            (db.models.GameServerState.time >= min_dt)
        )

    stmt = select(db.models.GameServerState).where(
        *wheres
    ).options(
        load_only(
            db.models.GameServerState.game_server_port,
            db.models.GameServerState.game_server_address,
            db.models.GameServerState.players,
            db.models.GameServerState.max_players,
            db.models.GameServerState.a2s_info_responded,
            db.models.GameServerState.a2s_player_count,
            db.models.GameServerState.a2s_max_players,
            db.models.GameServerState.a2s_rules_responded,
            db.models.GameServerState.a2s_num_public_connections,
            db.models.GameServerState.a2s_num_open_public_connections,
            db.models.GameServerState.a2s_pi_count,
            db.models.GameServerState.a2s_pi_objects,
            db.models.GameServerState.a2s_players_responded,
            db.models.GameServerState.a2s_players,
            db.models.GameServerState.secure,
            db.models.GameServerState.map,
            db.models.GameServerState.a2s_map_name,
            db.models.GameServerState.a2s_mutators_running,
        )
    )

    if timedelta is None:
        stmt = stmt.execution_options(
            yield_per=1000,
        )  # .limit(2000)  # TODO: limit is temporary!

    update_wheres = [
        (db.models.GameServerState.game_server_port == bindparam("u_game_server_port"))
        & (db.models.GameServerState.game_server_address == bindparam("u_game_server_address"))
        & (db.models.GameServerState.time == bindparam("u_time"))
    ]

    with app.db_session.begin() as sess:
        states = sess.scalars(stmt)

        sess.connection().execute(
            update(db.models.GameServerState).where(
                *update_wheres,
            ),
            [
                {
                    "u_game_server_port": state.game_server_port,
                    "u_game_server_address": state.game_server_address,
                    "u_time": state.time,
                    "trust_score": trust.eval_trust_score(state)
                }
                for state in states
            ],
        )


@app.task(ignore_result=True)
def query_servers():
    # TODO: need to be able to detect overlapping queries?
    with app.db_session() as sess:
        settings = sess.scalars(
            select(
                db.models.QuerySettings
            ).where(
                db.models.QuerySettings.is_active
            ).options(
                load_only(
                    db.models.QuerySettings.name,
                    db.models.QuerySettings.query_params,
                )
            )
        )
        qp = [
            (
                s.name,
                s.query_params,
            )
            for s in settings
        ]

    for name, query_params in qp:
        rand_delay = random.uniform(
            DISCOVER_DELAY_MIN, DISCOVER_DELAY_MAX)

        logger.info("starting discovery: '%s' '%s' in %s",
                    name, query_params, rand_delay)

        discover_servers.apply_async(
            (query_params,),
            countdown=rand_delay,
            expires=QUERY_INTERVAL + rand_delay + 1,
        )


@app.task(ignore_result=True)
def discover_servers(query_params: Dict[str, str | int]):
    # Don't allow empty filters for now.
    query_filter = str(query_params["filter"])
    limit = int(query_params.get("limit", 0))
    server_results = list(webapi().get_server_list(query_filter, limit))

    if not server_results:
        logger.warning("did not get any server results for query: %s",
                       query_params)
        return

    # Randomize order to normalize delays between discovery to queries.
    random.shuffle(server_results)

    # TODO: error handling here? Sanitize Steam API response?

    stmt = pg_insert(db.models.GameServer).values(
        [
            {
                "address": ipaddress.IPv4Address(sr.addr),
                "port": sr.gameport,
                "query_port": int(sr.query_port),
            }
            for sr in server_results
        ]
    )
    on_update_stmt = stmt.on_conflict_do_update(
        index_elements=["address", "port"],
        set_={"query_port": stmt.excluded.query_port},
    )

    with app.db_session.begin() as sess:
        sess.execute(on_update_stmt)

    for sr in server_results:
        query_server_state.apply_async(
            (dataclasses.asdict(sr),),
            expires=QUERY_INTERVAL,
        )


@app.task(ignore_result=True)
def query_server_state(server: Dict[str, Any]):
    gs_result = GameServerResult(**server)
    a2s_addr = (gs_result.addr, gs_result.query_port)
    gameport = gs_result.gameport

    # TODO: this should be set earlier, when the Steam API request
    #   happens? That would be closer to reality.
    query_time = datetime.datetime.now(tz=datetime.timezone.utc)

    with app.db_session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=gs_result.addr,
            game_server_port=gameport,
            steamid=gs_result.steamid,
            name=gs_result.name,
            appid=gs_result.appid,
            gamedir=gs_result.gamedir,
            version=gs_result.version,
            product=gs_result.product,
            region=gs_result.region,
            players=gs_result.players,
            max_players=gs_result.max_players,
            bots=gs_result.bots,
            map=gs_result.map,
            secure=gs_result.secure,
            dedicated=gs_result.dedicated,
            os=gs_result.os,
            gametype=gs_result.gametype,
        )
        sess.add(state)

    a2s_tasks.a2s_info.apply_async(
        (a2s_addr, gameport, query_time),
        expires=A2S_TASK_EXPIRY,
    )
    a2s_tasks.a2s_rules.apply_async(
        (a2s_addr, gameport, query_time),
        expires=A2S_TASK_EXPIRY,
    )
    a2s_tasks.a2s_players.apply_async(
        (a2s_addr, gameport, query_time),
        expires=A2S_TASK_EXPIRY,
    )

    do_icmp_request.apply_async(
        (gs_result.addr, gameport, query_time),
        expires=A2S_TASK_EXPIRY,
    )


@app.task(ignore_result=True)
def do_icmp_request(
        game_server_addr: str,
        game_server_port: int,
        query_time: datetime.datetime
):
    resp = icmplib.ping(
        game_server_addr,
        interval=0.5,
        count=2,
        timeout=5,
        privileged=False,
    )
    is_alive = resp.is_alive
    logger.info(
        "%s ping response: is_alive=%s avg_rtt=%s jitter=%s packet_loss=%s",
        game_server_addr, is_alive, resp.avg_rtt, resp.jitter,
        resp.packet_loss,

    )
    with app.db_session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=game_server_addr,
            game_server_port=game_server_port,
            icmp_responded=is_alive,
        )
        sess.merge(state)


@app.task(ignore_result=True)
def cache_trust_aggregate():
    r = redis_client()
    lock = redis.lock.Lock(
        r,
        name=TRUST_LOCK_KEY,
        blocking=True,
        blocking_timeout=30.0,
        timeout=30.0,
    )

    acquired = lock.acquire()
    if not acquired:
        logger.error("cache_trust_aggregate unable to acquire lock")
        return

    try:
        coder = coding.ZstdMsgPackCoder()
        with app.db_session.begin() as sess:
            vals = _select_trust_aggregate(sess)
            packed = coder.encode(vals)
            logger.info("caching trust values (len=%s) (size=%s)",
                        len(vals), len(packed))
            r.set(
                name=TRUST_KEY,
                value=packed,
                ex=datetime.timedelta(hours=24),
            )
    except Exception as e:
        logger.exception("cache_trust_aggregate error: %s", e)
    finally:
        if acquired:
            lock.release()


# TODO: deduplicate this?
def _select_trust_aggregate(
        session: sqlalchemy.orm.Session
) -> list[tuple[ipaddress.IPv4Address, tuple[int, ...], tuple[float, ...]]]:
    params = {"cutoff": 0.31}
    ret = []
    for row in session.execute(db.queries.trust_aggregate, params):
        len1 = len(row[1])
        len2 = len(row[2])
        if len1 != len2:
            logger.error("agg list lengths don't match: %s != %s",
                         len1, len2)
        ret.append((row[0], row[1], row[2]))
    return ret
