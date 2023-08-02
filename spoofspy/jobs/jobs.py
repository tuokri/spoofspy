from celery import Celery

app = Celery()


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    sender.add_periodic_task(5 * 60, get_steam_server_info.s())

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


@app.task
def discover_servers():
    pass


@app.task
def get_steam_server_info():
    pass

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
