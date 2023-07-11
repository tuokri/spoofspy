import os
from typing import Any
from typing import Optional
from typing import TypeVar

import sqlalchemy.exc
from psycopg_pool import ConnectionPool
from psycopg_pool import NullConnectionPool
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session as _ORMSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import DropTable

from spoofspy.db.models import AutomapModel
from spoofspy.db.models import BaseModel

_pool: Optional[ConnectionPool] = None
_engine: Optional[Engine] = None

_Session = TypeVar("_Session", bound=_ORMSession)


def engine() -> Engine:
    global _pool
    global _engine

    connect_args = {}

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

    try:
        if not AutomapModel.classes:
            AutomapModel.prepare(autoload_with=_engine)
    except sqlalchemy.exc.NoReferencedTableError:
        # TODO: happens when entering data to a fresh database.
        #   Think of a smart way to handle this.
        pass

    return _engine


# noinspection PyPep8Naming
class session_maker(sessionmaker):
    def __call__(self, **local_kw: Any) -> _ORMSession:
        local_kw["bind"] = engine()
        return super().__call__(**local_kw)


Session: sessionmaker = session_maker()


def drop_create_all(db_engine: Optional[Engine] = None):
    @compiles(DropTable, "postgresql")
    def _compile_drop_table(element, compiler):
        return f"{compiler.visit_drop_table(element)} CASCADE"

    if db_engine is None:
        db_engine = engine()

    db_engine.dispose(close=False)

    BaseModel.metadata.drop_all(db_engine)
    BaseModel.metadata.create_all(db_engine)

    # TODO:
    # with Session() as s, s.begin():
    #     _timescale_sql = (
    #             Path(__file__).parent / "timescale.sql").read_text()
    #     _c = s.connection().connection.cursor()
    #     _c.execute(_timescale_sql)

    if not AutomapModel.classes:
        AutomapModel.prepare(autoload_with=db_engine)
