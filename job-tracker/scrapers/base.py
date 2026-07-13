"""
Every scraper — static, dynamic, or RSS — implements this same interface.
The orchestrator (main.py) doesn't care which type a site is; it just calls
.scrape() and handles whatever list of JobListing comes back, wrapping each
call so one broken site can't take down the whole run.
"""
from abc import ABC, abstractmethod

from core.models import JobListing


class BaseScraper(ABC):
    def __init__(self, site_config: dict):
        self.config = site_config
        self.name = site_config["name"]
        self.url = site_config["url"]

    @abstractmethod
    def scrape(self) -> list[JobListing]:
        """Fetch and parse job listings. Must return a list, even if empty."""
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.__class__.__name__} site={self.name!r}>"
