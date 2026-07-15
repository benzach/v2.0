"""
Maps a site's configured `type` (static / dynamic / rss) to the scraper
class that handles it, and loads config/sites.yaml.
"""
import yaml

from scrapers.base import BaseScraper
from scrapers.static_scraper import StaticScraper
from scrapers.dynamic_scraper import DynamicScraper
from scrapers.rss_scraper import RSSScraper
from scrapers.adzuna_scraper import AdzunaScraper
from scrapers.reed_scraper import ReedScraper

SCRAPER_TYPES: dict[str, type[BaseScraper]] = {
    "static": StaticScraper,
    "dynamic": DynamicScraper,
    "rss": RSSScraper,
    "adzuna": AdzunaScraper,
    "reed": ReedScraper,
}


def load_site_configs(path: str = "config/sites.yaml") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def build_scrapers(site_configs: list[dict], only_site: str | None = None) -> list[BaseScraper]:
    """
    Instantiates the correct scraper for each enabled site config.
    If `only_site` is given, restricts to that one site (used for
    `python main.py --site <name>` debugging), ignoring its enabled flag
    so you can test disabled/in-progress sites directly.
    """
    scrapers = []
    for cfg in site_configs:
        if only_site:
            if cfg["name"] != only_site:
                continue
        elif not cfg.get("enabled", True):
            continue

        scraper_cls = SCRAPER_TYPES.get(cfg["type"])
        if not scraper_cls:
            raise ValueError(f"Unknown scraper type '{cfg['type']}' for site '{cfg['name']}'")
        scrapers.append(scraper_cls(cfg))
    return scrapers
