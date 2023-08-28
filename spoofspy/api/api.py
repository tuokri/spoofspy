import os

from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import load_only

from spoofspy import db
from spoofspy.api import coding

app = FastAPI()

AsyncSession: async_sessionmaker


# TODO: better, row based caching.
# TODO: use middleware to ignore Cache-Control?

@app.get("/game-server-state/")
@cache(expire=600)
async def root():
    async with AsyncSession() as sess:
        stmt = select(db.models.GameServerState).options(
            load_only(
                db.models.GameServerState.game_server_address,
                db.models.GameServerState.game_server_port,
                db.models.GameServerState.steamid,
                db.models.GameServerState.name,
                db.models.GameServerState.appid,
                db.models.GameServerState.gamedir,
                db.models.GameServerState.version,
                db.models.GameServerState.product,
                db.models.GameServerState.players,
                db.models.GameServerState.max_players,
                db.models.GameServerState.bots,
                db.models.GameServerState.map,
                db.models.GameServerState.secure,
                db.models.GameServerState.a2s_info_responded,
                db.models.GameServerState.a2s_player_count,
                db.models.GameServerState.a2s_max_players,
                db.models.GameServerState.a2s_rules_responded,
                db.models.GameServerState.a2s_num_open_public_connections,
                db.models.GameServerState.a2s_num_public_connections,
                db.models.GameServerState.a2s_pi_count,
                db.models.GameServerState.a2s_pi_objects,
                db.models.GameServerState.a2s_players_responded,
                db.models.GameServerState.a2s_players,
                db.models.GameServerState.trust_score,
            )
        )

        ret = []
        for x in await sess.scalars(stmt):
            ret.append(await x.async_to_dict(ignore_deferred=True))

        return ret


@app.on_event("startup")
async def on_startup():
    global AsyncSession
    AsyncSession = async_sessionmaker(await db.async_engine())

    r = redis.StrictRedis().from_url(os.environ["REDIS_URL"])
    FastAPICache.init(RedisBackend(r),
                      prefix="fastapi-cache",
                      coder=coding.MsgPackCoder)


@app.on_event("shutdown")
async def on_shutdown():
    await db.async_close_database()

# REST API that's effectively a layer on top of the DB/ORM.
