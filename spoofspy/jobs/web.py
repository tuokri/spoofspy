import steam.webapi


class WebAPI:
    def __init__(self, key: str):
        self.api = steam.webapi.WebAPI(key)
