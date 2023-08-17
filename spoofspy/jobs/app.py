import os

from celery import Celery
from kombu.serialization import register

from spoofspy.jobs import serializer

register(
    "msgpack_dt",
    serializer.dumps,
    serializer.loads,
    content_type="application/x-msgpack",
    content_encoding="utf-8",
)

REDIS_URL = os.environ["REDIS_URL"]
app = Celery(
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
