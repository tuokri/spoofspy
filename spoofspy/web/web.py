import ssl
from dataclasses import dataclass
from typing import List
from typing import Optional
from urllib.parse import urlencode
from urllib.parse import urlunparse

import httpx
import orjson

SSL_CONTEXT = ssl.create_default_context()


@dataclass(frozen=True, slots=True)
class GameServerResult:
    addr: str
    gameport: int
    query_port: int
    steamid: Optional[int] = None
    name: Optional[str] = None
    appid: Optional[int] = None
    gamedir: Optional[str] = None
    version: Optional[str] = None
    product: Optional[str] = None
    region: Optional[int] = None
    players: Optional[int] = None
    max_players: Optional[int] = None
    bots: Optional[int] = None
    map: Optional[str] = None
    secure: Optional[bool] = None
    dedicated: Optional[bool] = None
    os: Optional[str] = None
    gametype: Optional[str] = None


# TODO: do we need a more generalized Steam Web API wrapper?
#   steam.webapi lacks the endpoints we need.
# TODO: move this to its own module?
class SteamWebAPI:
    # Total number of requests made to Steam Web API
    # in all SteamWebAPI instances.
    api_requests: int = 0

    def __init__(self, key: str):
        self._key = key
        # TODO: redact sensitive information from httpx logs.
        self._client = httpx.Client(verify=SSL_CONTEXT)

    def __del__(self):
        self._client.close()

    def get_server_list(
            self,
            query_filter: str = "",
            limit: int = 0,
    ) -> List[GameServerResult]:
        """IGameServersService/GetServerList
        TODO: error handling? Logging?
        """
        params = {
            "key": self._key,
        }
        if query_filter:
            params["filter"] = query_filter
        if limit:
            params["limit"] = limit

        url = urlunparse((
            "https",  # scheme
            "api.steampowered.com",  # netloc
            "/IGameServersService/GetServerList/v1/",  # url
            None,  # query
            urlencode(params),  # params
            None,  # fragment
        ))

        resp = self._client.get(url)
        self.api_requests += 1
        servers = orjson.loads(resp.content)["response"]["servers"]

        ret = []
        for server in servers:
            addr, query_port = server["addr"].split(":")
            gsr = GameServerResult(
                addr=addr,
                query_port=int(query_port),
                gameport=server["gameport"],
                steamid=server.get("steamid", None),
                name=server.get("name", None),
                appid=server.get("appid", None),
                gamedir=server.get("gamedir", None),
                version=server.get("version", None),
                product=server.get("product", None),
                region=server.get("region", None),
                players=server.get("players", None),
                max_players=server.get("max_players", None),
                bots=server.get("bots", None),
                map=server.get("map", None),
                secure=server.get("secure", None),
                dedicated=server.get("dedicated", None),
                os=server.get("os", None),
                gametype=server.get("gametype", None),
            )
            ret.append(gsr)

        return ret