import datetime
import ipaddress
from typing import Any
from typing import List

import sqlalchemy
from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import DeferredReflection
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


class BaseModel(PrettyReprMixin, AsyncAttrs, DeclarativeBase):
    __abstract__ = True

    def to_dict(self, ignore_unloaded=False) -> dict:
        ignored_keys = set()
        if ignore_unloaded:
            # noinspection PyUnresolvedReferences
            ignored_keys.update(inspect(self).unloaded)

        keys = [
            k for k in self.__mapper__.c.keys()
            if k not in ignored_keys
        ]

        d = {
            key: getattr(self, key)
            for key in keys
            if not key.startswith("_")
        }
        d_hybrid = {
            key: getattr(self, key)
            for key, prop in inspect(self.__class__).all_orm_descriptors.items()
            if isinstance(prop, hybrid_property)
        }
        d.update(d_hybrid)

        return d

    async def async_to_dict(self, ignore_unloaded=False) -> dict:
        ignored_keys = set()
        if ignore_unloaded:
            # noinspection PyUnresolvedReferences
            ignored_keys.update(inspect(self).unloaded)

        keys = [
            k for k in self.__mapper__.c.keys()
            if k not in ignored_keys
        ]

        d = {
            key: await getattr(self.awaitable_attrs, key)
            for key in keys
            if not key.startswith("_")
        }
        # d_hybrid = {
        #     key: getattr(self, key)
        #     for key, prop in inspect(self.__class__).all_orm_descriptors.items()
        #     if isinstance(prop, hybrid_property)
        # }
        # d.update(d_hybrid)

        return d


class QueryStatistics(BaseModel):
    # TODO: this could simply be a name-value table.
    #   E.g. name(text) - value(bigint):
    #   steam_web_api_queries   -  x
    #   some_other_query_state  -  y

    __tablename__ = "query_statistics"

    id: Mapped[bool] = mapped_column(
        Boolean,
        primary_key=True,
        unique=True,
        default=True,
    )

    steam_web_api_queries: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    # Enforce only a single row allowed.
    CheckConstraint(
        "id CHECK (id)"
    )


# TODO: reconsider plural names?
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
        return "\\".join(
            f"{key}\\{value}"
            for key, value in self.query_params.items()
        )


class GameServer(BaseModel):
    """Steam game server. Identified by IP:PORT."""
    __tablename__ = "game_server"

    # TODO: common base class to allow both IPv4 and IPv6?
    address: Mapped[ipaddress.IPv4Address] = mapped_column(
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


class ReflectedBase(DeferredReflection):
    __abstract__ = True


class TimescaleModel(BaseModel):
    """TimescaleDB hypertable."""
    __abstract__ = True

    time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        primary_key=True,  # TODO: this is not actually true?
    )


class GameServerState(ReflectedBase, TimescaleModel):
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
    gametype: Mapped[str] = mapped_column(Text, nullable=True, deferred=True)

    # A2S info fields.
    a2s_info_responded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True,
    )
    a2s_info_response_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    a2s_server_name: Mapped[str] = mapped_column(Text, nullable=True)
    a2s_map_name: Mapped[str] = mapped_column(Text, nullable=True)
    a2s_steam_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    a2s_player_count: Mapped[int] = mapped_column(Integer, nullable=True)
    a2s_max_players: Mapped[int] = mapped_column(Integer, nullable=True)
    a2s_open_slots: Mapped[int] = mapped_column(Integer, nullable=True)
    # Leftover fields in their raw format.
    a2s_info: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB,
        nullable=True,
        deferred=True,
    )

    # A2S rules fields.
    a2s_rules_responded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True,
    )
    a2s_rules_response_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    a2s_num_open_public_connections: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    a2s_num_public_connections: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    # Presumably "player info count"?
    a2s_pi_count: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    a2s_pi_objects: Mapped[dict[str, dict]] = mapped_column(
        postgresql.JSONB,
        nullable=True,
    )
    a2s_mutators_running: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(Text),
        nullable=True,
    )
    # Leftovers.
    a2s_rules: Mapped[dict[str, str]] = mapped_column(
        postgresql.JSONB,
        nullable=True,
        deferred=True,
    )

    # A2S players fields.
    a2s_players_responded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True,
    )
    a2s_players_response_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    trust_score: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    icmp_responded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True,
    )

    __table__args = (
        ForeignKeyConstraint(
            [game_server_address, game_server_port],
            [GameServer.address, GameServer.port],
        )
    )


class EndpointAccess(ReflectedBase, TimescaleModel):
    __tablename__ = "endpoint_access"

    address: Mapped[ipaddress.IPv4Address] = mapped_column(
        postgresql.INET,
        nullable=False,
    )
    unique_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
