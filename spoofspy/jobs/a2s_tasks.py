import datetime
from typing import Tuple
from typing import Union

import a2s

from spoofspy import db
from spoofspy.jobs.app import app

# TODO: error handling.

A2S_TIMEOUT = 10.0


@app.task(ignore_result=True)
def a2s_info(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)

    info = a2s.info(addr, timeout=A2S_TIMEOUT)
    info_fields = {
        key: value for
        key, value in info
    }

    with db.Session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_server_name=info_fields.pop("server_name"),
            a2s_map_name=info_fields.pop("map_name"),
            a2s_steam_id=info_fields.pop("steam_id"),
            a2s_player_count=info_fields.pop("player_count"),
            a2s_max_players=info_fields.pop("max_players"),
            a2s_info=info_fields,
        )
        sess.merge(state)


@app.task(ignore_result=True)
def a2s_rules(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)
    rules = a2s.rules(addr, timeout=A2S_TIMEOUT)

    with db.Session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_rules=rules,
        )
        sess.merge(state)


@app.task(ignore_result=True)
def a2s_players(
        addr: Tuple[str, int],
        gameport: int,
        query_time: datetime.datetime,
):
    addr = _coerce_tuple(addr)

    players = a2s.players(addr, timeout=A2S_TIMEOUT)
    players = [
        {
            key: value
            for key, value in player
        } for player in players
    ]

    with db.Session.begin() as sess:
        state = db.models.GameServerState(
            time=query_time,
            game_server_address=addr[0],
            game_server_port=gameport,
            a2s_players=players,
        )
        sess.merge(state)


def _coerce_tuple(x: Union[list, tuple]) -> Tuple:
    # Celery converts tuples to lists.
    return x[0], x[1]
