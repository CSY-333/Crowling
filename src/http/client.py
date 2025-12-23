import requests

from src.interfaces import IHttpClient


class RequestsHttpClient(IHttpClient):
    """
    Thin adapter over requests.Session that satisfies IHttpClient.
    """

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def request(self, method: str, url: str, **kwargs):
        return self.session.request(method=method, url=url, **kwargs)
