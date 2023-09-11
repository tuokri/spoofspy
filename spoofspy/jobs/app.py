import os

from celery import Celery
from celery.signals import worker_init
from celery.signals import worker_shutdown
from celery.utils.log import get_logger
from kombu.serialization import register
from sqlalchemy.orm import sessionmaker

from spoofspy import db
from spoofspy.jobs import serialization

logger = get_logger(__name__)

register(
    "msgpack_dt",
    serialization.dumps,
    serialization.loads,
    content_type="application/msgpack",
    content_encoding="binary",
)


@worker_init.connect
def _init_worker(*_args, **_kwargs):
    # TODO: this can fail quietly?
    app._db_session = sessionmaker(db.engine())


@worker_shutdown.connect
def _shutdown_worker(*_args, **_kwargs):
    db.close_database()


REDIS_URL = os.environ["REDIS_URL"]


class CustomCelery(Celery):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._db_session: sessionmaker | None = None

    @property
    def db_session(self) -> sessionmaker:
        # This should be done in `worker_init` before we even
        # get here, but somehow this has happened (although very rarely)
        # during development and testing.
        if not self._db_session:
            logger.warn("_db_session not initialized, performing late init!")
            self._db_session = sessionmaker(db.engine())

        return self._db_session


_accept_content = [
    "application/json",
    "application/msgpack",
    "application/x-msgpack",
]
app = CustomCelery(
    "app",
    backend=REDIS_URL,
    broker=REDIS_URL,
    broker_connection_retry_on_startup=True,
    task_serializer="msgpack_dt",
    result_serializer="msgpack_dt",
    accept_content=_accept_content,
    task_accept_content=_accept_content,
    result_accept_content=_accept_content,
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
