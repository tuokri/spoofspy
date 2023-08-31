import dataclasses
import datetime
import ipaddress
import logging
import os
import random
from typing import Any
from typing import Dict
from typing import Optional

from celery import Celery
from celery.signals import beat_init
from celery.utils.log import get_logger
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.orm import load_only

from spoofspy import db
from spoofspy.heuristics import trust
from spoofspy.jobs import a2s_tasks
from spoofspy.jobs.app import app
from spoofspy.web import GameServerResult
from spoofspy.web import SteamWebAPI

DISCOVER_DELAY_MIN = 0.0
DISCOVER_DELAY_MAX = 10.0

_webapi: Optional[SteamWebAPI] = None

logger: logging.Logger = get_task_logger(__name__)
beat_logger: logging.Logger = get_logger(f"beat.{__name__}")


def webapi() -> SteamWebAPI:
    global _webapi
    if _webapi is None:
        _webapi = SteamWebAPI(key=os.environ["STEAM_WEB_API_KEY"])
    return _webapi


if os.environ.get("SPOOFSPY_DEBUG"):
    QUERY_INTERVAL = EVAL_INTERVAL = 1 * 60
else:
    QUERY_INTERVAL = EVAL_INTERVAL = 5 * 60


@beat_init.connect
def beat_init(*_args, **_kwargs):
    beat_logger.info("using QUERY_INTERVAL=%s", QUERY_INTERVAL)
    beat_logger.info("using EVAL_INTERVAL=%s", EVAL_INTERVAL)


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **_kwargs):
    sender.add_periodic_task(QUERY_INTERVAL, query_servers.s())
    sender.add_periodic_task(EVAL_INTERVAL, eval_server_trust_scores.s())

    # TODO: Also need an eval job that runs less often but checks old,
    #   "missed" entries and evaluates them?


@app.task(ignore_result=True)
def eval_server_trust_scores():
    min_dt = datetime.datetime.now(tz=datetime.timezone.utc)
    min_dt -= datetime.timedelta(seconds=EVAL_INTERVAL * 2)
    with app.db_session.begin() as sess:
        stmt = select(db.models.GameServerState).where(
            (db.models.GameServerState.time >= min_dt)
            & (db.models.GameServerState.trust_score.is_(None))
            & (db.models.GameServerState.a2s_info_responded.is_not(None))
            & (db.models.GameServerState.a2s_rules_responded.is_not(None))
            & (db.models.GameServerState.a2s_players_responded.is_not(None))
        ).options(
            load_only(
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
            )
        )
        states = sess.scalars(stmt)

        for state in states:
            try:
                trust_score = trust.eval_trust_score(state)
                logger.info("%s: score: %s", state, trust_score)
            except Exception as e:
                logger.exception("error evaluating trust score: %s", e)
            sess.merge(state)


@app.task(ignore_result=True)
def query_servers():
    # TODO: need to be able to detect overlapping queries?
    with app.db_session() as sess:
        settings = sess.scalars(
            select(db.models.QuerySettings).where(
                db.models.QuerySettings.is_active
            ).options(
                load_only(
                    db.models.QuerySettings.query_params,
                )
            )
        )
        qp = [s.query_params for s in settings]

    for query_params in qp:
        rand_delay = random.uniform(
            DISCOVER_DELAY_MIN, DISCOVER_DELAY_MAX)
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

    # TODO: drop old entries based on some criteria?
    with app.db_session.begin() as sess:
        for sr in server_results:
            server = db.models.GameServer(
                address=ipaddress.IPv4Address(sr.addr),
                port=sr.gameport,
                query_port=int(sr.query_port),
            )
            sess.merge(server)

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
        sess.merge(state)

    a2s_tasks.a2s_info.delay(a2s_addr, gameport, query_time)
    a2s_tasks.a2s_rules.delay(a2s_addr, gameport, query_time)
    a2s_tasks.a2s_players.delay(a2s_addr, gameport, query_time)
