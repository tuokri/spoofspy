import datetime
from typing import Any

import sqlalchemy
from sqlalchemy import DateTime
from sqlalchemy import inspect
from sqlalchemy.ext.automap import AutomapBase
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class PrettyReprMixin:
    def _repr(self, **fields: Any) -> str:
        field_strings = []
        at_least_one_attached_attribute = False
        for key, field in fields.items():
            try:
                field_strings.append(f"{key}={field!r}")
            except sqlalchemy.orm.exc.DetachedInstanceError:
                field_strings.append(f"{key}=DetachedInstanceError")
            else:
                at_least_one_attached_attribute = True
        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"
        return f"<{self.__class__.__name__} {id(self)}>"


class BaseModel(PrettyReprMixin, DeclarativeBase):
    __abstract__ = True

    def to_dict(self) -> dict:
        d = {
            key: getattr(self, key)
            for key in self.__mapper__.c.keys()
            if not key.startswith("_")

        }
        d_hybrid = {
            key: getattr(self, key)
            for key, prop in inspect(self.__class__).all_orm_descriptors.items()
            if isinstance(prop, hybrid_property)
        }

        d.update(d_hybrid)
        return d


_AutomapBase: AutomapBase = automap_base()


class AutomapModel(PrettyReprMixin, _AutomapBase):
    __abstract__ = True


class Settings(BaseModel):
    """Application settings
    - Steam server query parameters.
        - Which gamedirs, addresses etc. to query.
    - Other settings that have to be stored?
    """
    __tablename__ = "settings"


class GameServer(BaseModel):
    """Steam game server. Identified by IP:PORT."""
    __tablename__ = "game_server"


class TimescaleModel(BaseModel):
    """TimescaleDB hypertable."""

    __abstract__ = True

    time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        primary_key=True,
    )


class GameServerState(TimescaleModel):
    """State(s) of queried server at given time.
    - A2S Rules.
    - A2S Info.
    - A2S State.
    - WebAPI based state(s).
    """
    __tablename__ = "game_server_state"
