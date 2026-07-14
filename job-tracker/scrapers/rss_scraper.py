"""
RSS scraper — for sites that publish an official feed (like w4mpjobs).
Far more reliable than HTML scraping: no selectors to maintain, no risk of
being blocked as a bot, and the site explicitly intends this data to be
consumed programmatically.
"""
import feedparser

from core.models import JobListing
from core.parsing import detect_contract_type
from scrapers.base import BaseScraper


class RSSScraper(BaseScraper):
    def scrape(self) -> list[JobListing]:
        feed = feedparser.parse(self.url)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse RSS feed for {self.name}: {feed.bozo_exception}")

        jobs = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            description = entry.get("summary", "").strip()
            posted = entry.get("published", "")

            if not title or not url:
                continue

            jobs.append(
                JobListing(
                    site=self.name,
                    title=title,
                    url=url,
                    description=description,
                    posted_date=posted,
                    contract_type=detect_contract_type(title, description),
                )
            )
        return jobs
