import os

from celery import Celery
from celery.signals import worker_init
from celery.signals import worker_shutdown
from kombu.serialization import register
from sqlalchemy.orm import sessionmaker

from spoofspy import db
from spoofspy.jobs import serialization

_Session: sessionmaker

register(
    "msgpack_dt",
    serialization.dumps,
    serialization.loads,
    content_type="application/msgpack",
    content_encoding="utf-8",
)


@worker_init.connect
def _init_worker(**_kwargs):
    global _Session
    _Session = sessionmaker(db.engine())
    app.db_session = _Session


@worker_shutdown.connect
def _shutdown_worker(**_kwargs):
    db.close_database()


REDIS_URL = os.environ["REDIS_URL"]


class CustomCelery(Celery):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        db_session: sessionmaker


app = CustomCelery(
    "app",
    backend=REDIS_URL,
    broker=REDIS_URL,
    broker_connection_retry_on_startup=True,
    task_serializer="msgpack_dt",
    result_serializer="msgpack_dt",
    accept_content=["application/json", "application/x-msgpack"],
    task_accept_content=["application/json", "application/x-msgpack"],
    result_accept_content=["application/json", "application/x-msgpack"],
    task_routes={
        "spoofspy.jobs.tasks.*": {"queue": "MainQueue"},
        "spoofspy.jobs.a2s_tasks.*": {"queue": "A2SQueue"},
    },
    include=[
        "spoofspy.jobs.tasks",
        "spoofspy.jobs.a2s_tasks",
    ],
)

# NOTE: can't use msgpack as event_serializer.
# See: https://github.com/celery/celery/issues/8285
