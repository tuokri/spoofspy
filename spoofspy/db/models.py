import datetime
from typing import Any
from typing import List

import sqlalchemy
from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.automap import AutomapBase
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


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

    # TODO: is this good?
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


class QuerySettings(BaseModel):
    """Application query settings
    - Steam server query parameters.
        - Which gamedirs, addresses etc. to query.
    - Other settings that have to be stored?
    """
    __tablename__ = "query_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        autoincrement=True,
        primary_key=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    # Steam server query filter key-value pairs.
    query_params: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB,
        # nullable=True,
    )

    def query_params_str(self) -> str:
        return f"\\".join(
            f"{key}\\{value}"
            for key, value in self.query_params.items()
        )


class GameServer(BaseModel):
    """Steam game server. Identified by IP:PORT."""
    __tablename__ = "game_server"

    address = mapped_column(
        postgresql.INET,
        nullable=False,
        primary_key=True,
    )
    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        primary_key=True,
    )
    query_port: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    CheckConstraint(
        "port BETWEEN 0 AND 65353",
        name="check_port_range",
    )
    CheckConstraint(
        "(query_port BETWEEN 0 AND 65353) OR (query_port IS NULL)",
        name="check_query_port_range",
    )


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
    - A2S Info.
    - A2S Rules.
    - A2S Players.
    - WebAPI based state(s).
    """
    __tablename__ = "game_server_state"

    game_server_address = mapped_column(
        postgresql.INET,
        nullable=False,
    )
    game_server_port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    game_server: Mapped[GameServer] = relationship(
        foreign_keys=[game_server_address, game_server_port],
    )

    # IGameServersService/GetServerList state.
    # IP address, game port and query port stored in GameServer.
    # addr: Mapped[str] = mapped_column(Text, nullable=True)
    # gameport: Mapped[int] = mapped_column(Integer, nullable=True)
    steamid: Mapped[int] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=True)
    appid: Mapped[int] = mapped_column(Integer, nullable=True)
    gamedir: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(Text, nullable=True)
    product: Mapped[str] = mapped_column(Text, nullable=True)
    region: Mapped[int] = mapped_column(Integer, nullable=True)
    players: Mapped[int] = mapped_column(Integer, nullable=True)
    max_players: Mapped[int] = mapped_column(Integer, nullable=True)
    bots: Mapped[int] = mapped_column(Integer, nullable=True)
    map: Mapped[str] = mapped_column(Text, nullable=True)
    secure: Mapped[bool] = mapped_column(Boolean, nullable=True)
    dedicated: Mapped[bool] = mapped_column(Boolean, nullable=True)
    os: Mapped[str] = mapped_column(Text, nullable=True)
    gametype: Mapped[str] = mapped_column(Text, nullable=True)

    # A2S info fields.
    a2s_server_name: Mapped[str] = mapped_column(Text, nullable=True)
    a2s_map_name: Mapped[str] = mapped_column(Text, nullable=True)
    a2s_steam_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    a2s_player_count: Mapped[int] = mapped_column(Integer, nullable=True)
    a2s_max_players: Mapped[int] = mapped_column(Integer, nullable=True)
    # Leftover fields in their raw format.
    a2s_info: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB,
        nullable=True,
    )

    # A2S rules fields.
    a2s_rules: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB,
        nullable=True,
    )

    # A2S players fields.
    # Array of A2S player objects e.g.:
    # [
    #   {
    #       "index": 0,
    #       "name", "Player1",
    #       "score": 40,
    #       "duration": 0.00001,
    #   },
    #   {
    #       "index": 0,
    #       "name", "Ryan Gosling",
    #       "score": -1,
    #       "duration": 5.4501,
    #   },
    # ]
    a2s_players: Mapped[List[dict[str, str]]] = mapped_column(
        postgresql.ARRAY(postgresql.JSONB),
        nullable=True,
    )

    __table__args = (
        ForeignKeyConstraint(
            [game_server_address, game_server_port],
            [GameServer.address, GameServer.port],
        )
    )
