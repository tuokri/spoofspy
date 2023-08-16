import dataclasses
import ipaddress
import os
import random
from typing import Any
from typing import Dict
from typing import Tuple

from celery import Celery
from sqlalchemy import select

from spoofspy import db
from spoofspy.jobs import a2s
from spoofspy.jobs.web import GameServerResult
from spoofspy.jobs.web import SteamWebAPI

REDIS_URL = os.environ["REDIS_URL"]
app = Celery(
    "app",
    backend=REDIS_URL,
    broker=REDIS_URL,
    broker_connection_retry_on_startup=True,
)
beat_app = Celery(
    "beat_app",
    backend=REDIS_URL,
    broker=REDIS_URL,
    broker_connection_retry_on_startup=True,
)

webapi = SteamWebAPI(key=os.environ["STEAM_WEB_API_KEY"])

DISCOVER_DELAY_MIN = 0.0
DISCOVER_DELAY_MAX = 10.0


# class BaseTask(Task):
#     def on_failure(self, exc, task_id, args, kwargs, einfo):
#         logger.exception("task failed", exc_info=exc)
#         super().on_failure(exc, task_id, args, kwargs, einfo)


@beat_app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    # sender.add_periodic_task(5 * 60, query_servers.s())
    sender.add_periodic_task(1 * 60, query_servers.s())

    # Periodically get query settings from DB, then:
    # - Start periodic server discovery tasks for each query.
    # - Server discovery task will add or update servers to the
    #   servers table. Discovered servers are also queried for their
    #   A2S and Steam Web API states.


@app.task
def get_query_settings():
    pass
    # TODO: need to be able to detect overlapping queries?
    # For each query setting:
    #   Fire server discovery query task:
    #     For each discovered server:
    #       Add/update server table.
    #       Fire A2s and Web API state tasks.


@app.task(ignore_result=True)
def query_servers():
    # 1. Get query settings.
    # 2. Fire WebAPI queries.
    # 3. Fire more tasks based on discovered servers.
    with db.Session() as sess:
        settings = sess.scalars(
            select(db.models.QuerySettings).where(
                db.models.QuerySettings.is_active
            )
        )
        for setting in settings:
            rand_delay = random.uniform(
                DISCOVER_DELAY_MIN, DISCOVER_DELAY_MAX)
            discover_servers.apply_async(
                (setting.query_params,),
                countdown=rand_delay,
            )


@app.task(ignore_result=True)
def discover_servers(query_params: Dict[str, str]):
    # Don't allow empty filters for now.
    query_filter = query_params["filter"]
    limit = query_params.get("limit", 0)
    server_results = webapi.get_server_list(query_filter, limit)
    # Update game_server table.
    #   - create new entries
    #   - update existing entries
    #   - drop old entries based on some criteria?
    with db.Session.begin() as sess:
        for sr in server_results:
            server = db.models.GameServer(
                address=ipaddress.IPv4Address(sr.addr),
                port=sr.gameport,
                query_port=int(sr.query_port),
            )
            sess.merge(server)

    for sr in server_results:
        # TODO: dataclass is not JSON-serializable.
        #   Is there a better way to handle this?
        query_server_state.delay(dataclasses.asdict(sr))


@app.task(ignore_result=True)
def query_server_state(server: Dict[str, Any]):
    gs_result = GameServerResult(**server)
    addr = (gs_result.addr, gs_result.query_port)
    # TODO: need better mechanism for handling this?
    #  calling group().get() deadlocks.
    # TODO: use separate workers for A2
    # group = celery.group(
    #     a2s_info.s(addr),
    #     a2s_rules.s(addr),
    #     a2s_players.s(addr),
    # )
    # Use sequential blocking calls for now.
    info = a2s.server_info(addr)
    rules = a2s.server_rules(addr)
    players = a2s.server_players(addr)


@app.task
def a2s_info(addr: Tuple[str, int]):
    addr = _coerce_tuple(addr)
    return a2s.server_info(addr)


@app.task
def a2s_rules(addr: Tuple[str, int]):
    addr = _coerce_tuple(addr)
    return a2s.server_rules(addr)


@app.task
def a2s_players(addr: Tuple[str, int]):
    addr = _coerce_tuple(addr)
    return a2s.server_players(addr)


def _coerce_tuple(x) -> Tuple:
    # Celery converts tuples to lists.
    return x[0], x[1]

# TODO: need task to be able to fetch information for
#   selected servers based on some criteria. Separate
#   tasks for A2S and Web API based queries? A job for
#   "evaluating" fake servers?

# TODO:
#   1. Get query settings from database.
#   2. Start (async) query jobs with the loaded settings.
#       - check which gamedirs to query (IGameServersService/GetServerList \gamedir\XYZ)
#       - discover servers for the gamedir (ISteamApps/GetServersAtAddress)
#       - start background jobs for each server
#       -

# Server discovery job. Discover servers based on database-stored
# query settings. Discovery job runs periodically, updating the
# server table.

# Server query jobs. Launched by the server discovery job. Queries
# individual servers, stores their states.

# Should we only query servers discovered by the most recent discovery
# job? Or should we also query past servers for a certain period before
# "forgetting" about them?
