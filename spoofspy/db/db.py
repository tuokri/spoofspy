import atexit
import os
from pathlib import Path
from typing import Optional
from typing import Tuple
from typing import Type

from sqlalchemy import Engine
from sqlalchemy import NullPool
from sqlalchemy import Pool
from sqlalchemy import QueuePool
from sqlalchemy import URL
from sqlalchemy import create_engine
from sqlalchemy import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import DropTable

from spoofspy.db.models import BaseModel
from spoofspy.db.models import QuerySettings
from spoofspy.db.models import QueryStatistics
from spoofspy.db.models import ReflectedBase
from spoofspy.utils.deployment import is_prod_deployment

_engine: Optional[Engine] = None
_async_engine: Optional[AsyncEngine] = None


def close_database():
    if _engine:
        _engine.dispose(True)


async def async_close_database():
    if _async_engine:
        await _async_engine.dispose(True)


atexit.register(close_database)


def _engine_args() -> Tuple[dict, dict, URL]:
    connect_args = {
        "connect_timeout": 30,
    }
    pool_kwargs: dict[str, int | Type[Pool]]

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("no database URL")

    url = make_url(db_url)
    url = url.set(drivername="postgresql+psycopg")

    # Handled by PgBouncer.
    if is_prod_deployment():
        connect_args["prepare_threshold"] = None  # type: ignore[assignment]
        pool_kwargs = {
            "poolclass": NullPool,
        }
    else:
        # Development env pool.
        pool_kwargs = {
            "poolclass": QueuePool,
            "pool_size": 250,
        }

    return connect_args, pool_kwargs, url


def engine(
        reflect: bool = True,
        force_reinit: bool = False,
        dispose: bool = False,
) -> Engine:
    global _engine

    # TODO: should this only exist for dev env?
    if force_reinit:
        if _engine:
            _engine.dispose(True)
        del _engine
        _engine = None

    if _engine is None:
        connect_args, pool_kwargs, db_url = _engine_args()
        _engine = create_engine(
            url=db_url,
            connect_args=connect_args,
            **pool_kwargs,
        )

    if reflect:
        ReflectedBase.prepare(_engine)

    if dispose:
        # For multiprocessing cases.
        _engine.dispose(close=False)

    return _engine


async def async_engine(
        reflect: bool = True,
        force_reinit: bool = False,
        dispose: bool = False,
) -> AsyncEngine:
    global _async_engine

    # TODO: should this only exist for dev env?
    if force_reinit:
        if _async_engine:
            await _async_engine.dispose(True)
        del _async_engine
        _async_engine = None

    if _async_engine is None:
        connect_args, pool_kwargs, db_url = _engine_args()
        _async_engine = create_async_engine(
            url=db_url,
            connect_args=connect_args,
            **pool_kwargs,
        )

    if reflect:
        async with _async_engine.begin() as conn:
            await conn.run_sync(ReflectedBase.prepare)

    if dispose:
        await _async_engine.dispose(close=False)

    return _async_engine


# TODO: do we need async version of this?
def drop_create_all(db_engine: Optional[Engine] = None):
    @compiles(DropTable, "postgresql")
    def _compile_drop_table(element, compiler):
        return f"{compiler.visit_drop_table(element)} CASCADE"

    if db_engine is None:
        db_engine = engine(reflect=False)

    db_engine.dispose(close=False)

    BaseModel.metadata.drop_all(db_engine)
    BaseModel.metadata.create_all(db_engine)

    session = sessionmaker(db_engine)

    timescale_sql = text(
        (Path(__file__).parent / "timescale.sql").read_text())
    with session.begin() as sess:
        sess.execute(timescale_sql)

    ReflectedBase.prepare(db_engine)

    with session.begin() as sess:
        sess.add(QueryStatistics())

    if not is_prod_deployment():
        with session.begin() as sess:
            sess.add(QuerySettings(
                name="test query",
                is_active=True,
                query_params={
                    "filter": "\\gamedir\\rs2",
                    "limit": 999,
                }
            ))
