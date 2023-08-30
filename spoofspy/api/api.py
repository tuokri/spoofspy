import logging
import os
from ipaddress import IPv4Address
from typing import Annotated
from typing import Tuple

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import ORJSONResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import load_only
from starlette.responses import PlainTextResponse

from spoofspy import db
from spoofspy.api import coding

logger = logging.getLogger(__name__)

app = FastAPI(
    default_response_class=ORJSONResponse,
)

AsyncSession: async_sessionmaker


# TODO: better, row based caching.
# TODO: use middleware to ignore Cache-Control?
# TODO: don't access database directly from endpoints,
#   use another layer that handles caching more intelligently.

@app.get("/")
async def root():
    return PlainTextResponse("hello")


@app.get("/game-servers/")
@cache(expire=600)
async def game_servers(
        address: Annotated[list[IPv4Address] | None, Query()] = None,
        port: Annotated[list[int] | None, Query()] = None,
        query_port: Annotated[list[int] | None, Query()] = None,
):
    stmt = select(db.models.GameServer)

    if address:
        stmt = stmt.where(
            db.models.GameServer.address.in_(address),
        )
    if port:
        stmt = stmt.where(
            db.models.GameServer.port.in_(port),
        )
    if query_port:
        stmt = stmt.where(
            db.models.GameServer.query_port.in_(query_port),
        )

    async with AsyncSession() as sess:
        return [
            await x.async_to_dict(ignore_unloaded=True)
            for x in await sess.scalars(stmt)
        ]


@app.get("/game-servers/{sockaddr}/")
@cache(expire=600)
async def game_servers_sockaddr(sockaddr: str):
    addr, port = _parse_sockaddr(sockaddr)

    stmt = select(db.models.GameServer).where(
        (db.models.GameServer.address == addr)
        & (db.models.GameServer.port == port)
    )

    async with AsyncSession() as sess:
        scalars = list(await sess.scalars(stmt))
        if not scalars:
            raise HTTPException(status_code=404)
        return [
            await x.async_to_dict(ignore_unloaded=True)
            for x in scalars
        ]


# TODO: @app.get("/game-servers/{sockaddr}/states/")


@app.get("/game-server-states/")
@cache(expire=600, coder=coding.ZstdMsgPackCoder)
async def game_server_states(
        address: Annotated[list[IPv4Address] | None, Query()] = None,
        port: Annotated[list[int] | None, Query()] = None,
        limit: int = 1000,
):
    if limit > 1000:
        limit = 1000
    elif limit <= 0:
        limit = 1000

    stmt = select(db.models.GameServerState).options(
        load_only(
            db.models.GameServerState.game_server_address,
            db.models.GameServerState.game_server_port,
            db.models.GameServerState.steamid,
            db.models.GameServerState.name,
            db.models.GameServerState.appid,
            db.models.GameServerState.gamedir,
            db.models.GameServerState.version,
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
    ).limit(limit)

    if address:
        stmt = stmt.where(
            db.models.GameServerState.game_server_address.in_(address),
        )
    if port:
        stmt = stmt.where(
            db.models.GameServerState.game_server_port.in_(port),
        )

    async with AsyncSession() as sess:
        return [
            await x.async_to_dict(
                ignore_unloaded=True,
            )
            for x in await sess.scalars(stmt)
        ]


@app.get("/query-settings/")
async def query_settings():
    stmt = select(db.models.QuerySettings)
    async with AsyncSession() as sess:
        return [
            await x.async_to_dict(ignore_unloaded=True)
            for x in await sess.scalars(stmt)
        ]


@app.on_event("startup")
async def on_startup():
    global AsyncSession

    logging.basicConfig()

    AsyncSession = async_sessionmaker(await db.async_engine())

    r = redis.StrictRedis().from_url(os.environ["REDIS_URL"])
    FastAPICache.init(RedisBackend(r),
                      prefix="fastapi-cache",
                      coder=coding.MsgPackCoder)


@app.on_event("shutdown")
async def on_shutdown():
    await db.async_close_database()


def _parse_sockaddr(sockaddr: str) -> Tuple[IPv4Address, int]:
    try:
        parts = sockaddr.split(":")
        addr = IPv4Address(parts[0])
        port = int(parts[1])
        return addr, port
    except (ValueError, TypeError, IndexError) as e:
        logger.info("invalid sockaddr: %s", e)
        raise HTTPException(status_code=400)

# REST API that's effectively a layer on top of the DB/ORM.
