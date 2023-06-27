from celery import Celery

app = Celery()


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    sender.add_periodic_task(5 * 60, get_steam_server_info.s())


@app.task
def get_steam_server_info():
    pass

# TODO: need task to be able to fetch information for
#   selected servers based on some criteria. Separate
#   tasks for A2S and Web API based queries? A job for
#   "evaluating" fake servers?
