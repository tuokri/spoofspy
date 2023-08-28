import atexit
import os
from pathlib import Path
from typing import Optional

from psycopg_pool import AsyncConnectionPool
from psycopg_pool import AsyncNullConnectionPool
from psycopg_pool import ConnectionPool
from psycopg_pool import NullConnectionPool
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import DropTable

from spoofspy.db.models import BaseModel
from spoofspy.db.models import QuerySettings
from spoofspy.db.models import QueryStatistics
from spoofspy.db.models import ReflectedBase

_SPOOFSPY_DEBUG = os.environ.get("SPOOFSPY_DEBUG")

_pool: Optional[ConnectionPool] = None
_engine: Optional[Engine] = None
_async_pool: Optional[AsyncConnectionPool] = None
_async_engine: Optional[AsyncEngine] = None


def close_database():
    if _engine:
        _engine.dispose(True)
    if _pool:
        _pool.close()


async def async_close_database():
    if _async_engine:
        await _async_engine.dispose(True)
    if _async_pool:
        await _async_pool.close()


atexit.register(close_database)


def engine(force_reinit: bool = False) -> Engine:
    global _pool
    global _engine

    connect_args = {}

    # TODO: should this only exist for dev env?
    if force_reinit:
        if _engine:
            _engine.dispose(True)
        if _pool:
            _pool.close()
        del _engine
        del _pool
        _engine = None
        _pool = None

    if _pool is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("no database URL")

        # Handled by PgBouncer.
        if "FLY_APP_NAME" in os.environ:
            _pool = NullConnectionPool(
                conninfo=db_url,
            )
            connect_args = {"prepare_threshold": None}
        else:
            # Development env pool.
            _pool = ConnectionPool(
                conninfo=db_url,
            )

    if _engine is None:
        protocol = "postgresql+psycopg://"
        _engine = create_engine(
            url=protocol,
            creator=_pool.getconn,
            connect_args=connect_args,
        )

    ReflectedBase.prepare(_engine)

    # try:
    #     if not AutomapModel.classes:
    #         AutomapModel.prepare(autoload_with=_engine)
    # except sqlalchemy.exc.NoReferencedTableError:
    #     # TODO: happens when entering data to a fresh database.
    #     #   Think of a smart way to handle this.
    #     pass

    return _engine


async def async_engine(force_reinit: bool = False) -> AsyncEngine:
    global _async_pool
    global _async_engine

    connect_args = {}

    # TODO: should this only exist for dev env?
    if force_reinit:
        if _async_engine:
            await _async_engine.dispose(True)
        if _async_pool:
            await _async_pool.close()
        del _async_engine
        del _async_pool
        _async_engine = None
        _async_pool = None

    if _async_pool is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("no database URL")

        # Handled by PgBouncer.
        if "FLY_APP_NAME" in os.environ:
            _async_pool = AsyncNullConnectionPool(
                conninfo=db_url,
            )
            connect_args = {"prepare_threshold": None}
        else:
            # Development env pool.
            _async_pool = AsyncConnectionPool(
                conninfo=db_url,
            )

    if _async_engine is None:
        protocol = "postgresql+psycopg://"
        _async_engine = create_async_engine(
            url=protocol,
            async_creator=_async_pool.getconn,
            connect_args=connect_args,
        )

    async with _async_engine.begin() as conn:
        await conn.run_sync(ReflectedBase.prepare)

    # try:
    #     if not AutomapModel.classes:
    #         AutomapModel.prepare(autoload_with=_async_engine.sync_engine)
    # except sqlalchemy.exc.NoReferencedTableError:
    #     # TODO: happens when entering data to a fresh database.
    #     #   Think of a smart way to handle this.
    #     pass

    return _async_engine


# TODO: do we need async version of this?
def drop_create_all(db_engine: Optional[Engine] = None):
    @compiles(DropTable, "postgresql")
    def _compile_drop_table(element, compiler):
        return f"{compiler.visit_drop_table(element)} CASCADE"

    if db_engine is None:
        db_engine = engine()

    db_engine.dispose(close=False)

    BaseModel.metadata.drop_all(db_engine)
    BaseModel.metadata.create_all(db_engine)

    session = sessionmaker(db_engine)

    with session() as s, s.begin():
        _timescale_sql = (
                Path(__file__).parent / "timescale.sql").read_text()
        _c = s.connection().connection.cursor()
        _c.execute(_timescale_sql)

    ReflectedBase.prepare(db_engine)

    with session.begin() as sess:
        sess.add(QueryStatistics())

    if _SPOOFSPY_DEBUG:
        with session.begin() as sess:
            sess.add(QuerySettings(
                name="test query",
                is_active=True,
                query_params={
                    "filter": "\\gamedir\\rs2",
                    "limit": 999,
                }
            ))
