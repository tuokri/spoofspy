import os
from typing import Any

import orjson
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi_cache import Coder
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as redis
from sqlalchemy import select

from spoofspy import db

app = FastAPI()


class ORJsonCoder(Coder):
    @classmethod
    def encode(cls, value: Any) -> bytes:
        return orjson.dumps(
            value,
            default=jsonable_encoder,
            option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY,
        )

    @classmethod
    def decode(cls, value: bytes) -> Any:
        return orjson.loads(value)


@app.get("/game-server-state/")
@cache(expire=600)
async def root():
    with db.Session() as sess:
        stmt = select(db.models.GameServerState)
        return list(sess.scalars(stmt))


@app.on_event("startup")
async def on_startup():
    r = redis.StrictRedis().from_url(os.environ["REDIS_URL"])
    FastAPICache.init(RedisBackend(r),
                      prefix="fastapi-cache", coder=ORJsonCoder)

# REST API that's effectively a layer on top of the DB/ORM.
