from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Generator
from contextlib import contextmanager

class IHttpClient(ABC):
    @abstractmethod
    def request(self, method: str, url: str, **kwargs) -> Any:
        pass

class IEvidenceCollector(ABC):
    @abstractmethod
    def log_failed_request(self, method: str, url: str, status_code: int, error_type: str, headers: Dict, context: Dict, response_body: bytes = None):
        pass

class IThrottleController(ABC):
    @abstractmethod
    def wait(self, domain: str = "default"):
        pass

    @abstractmethod
    def update_stats(self, status_code: int):
        pass

class IStorageDAO(ABC):
    @abstractmethod
    @contextmanager
    def transaction(self) -> Generator:
        pass

    @abstractmethod
    def get_completed_articles(self, run_id: str) -> set:
        pass

    @abstractmethod
    def insert_comments(self, comments: List[Dict[str, Any]]):
        pass

    @abstractmethod
    def update_article_status(self, oid: str, aid: str, status: str):
        pass
