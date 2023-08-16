import ipaddress
import os
import random
from typing import Dict

from celery import Celery
from sqlalchemy import select

from spoofspy import db
from spoofspy.jobs.web import SteamWebAPI

REDIS_URL = os.environ["REDIS_URL"]
app = Celery(
    "app",
    backend=REDIS_URL,
    broker=REDIS_URL,
)
beat_app = Celery(
    "beat_app",
    backend=REDIS_URL,
    broker=REDIS_URL,
)

webapi: SteamWebAPI

TASK_RANDOM_DELAY_MIN = 0.0
TASK_RANDOM_DELAY_MAX = 10.0


@beat_app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    global webapi
    webapi = SteamWebAPI(key=os.environ["STEAM_WEB_API_KEY"])

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
            addr, query_port = sr.addr.split(":")
            server = db.models.GameServer(
                address=ipaddress.IPv4Address(sr.addr),
                port=sr.gameport,
                query_port=int(query_port),
            )
            sess.merge(server)


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
            TASK_RANDOM_DELAY_MIN, TASK_RANDOM_DELAY_MAX)
        discover_servers.apply_async(
            setting.query_params,
            countdown=rand_delay,
        )

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
