import steam.webapi


class WebAPI:
    def __int__(self, key: str):
        self.api = steam.webapi.WebAPI(key)
