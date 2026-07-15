"""
RSS scraper — for sites that publish an official feed (like w4mpjobs).
Far more reliable than HTML scraping: no selectors to maintain, no risk of
being blocked as a bot, and the site explicitly intends this data to be
consumed programmatically.
"""
import re

import feedparser

from core.models import JobListing
from core.parsing import detect_contract_type
from scrapers.base import BaseScraper

# w4mpjobs (and similarly-structured feeds) tend to embed location/salary
# as plain text within the description rather than as separate RSS fields
# — e.g. "Location: London. Salary: £33,840." Best-effort extraction only;
# if a feed doesn't follow this pattern, these just come back empty rather
# than breaking anything (dashboard filters degrade gracefully either way).
LOCATION_PATTERN = re.compile(r"Location:\s*([^.\n]+)", re.IGNORECASE)
SALARY_PATTERN = re.compile(r"Salary:\s*([^.\n]+)", re.IGNORECASE)


def _extract_field(pattern: re.Pattern, text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


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
                    location=_extract_field(LOCATION_PATTERN, description),
                    salary=_extract_field(SALARY_PATTERN, description),
                    contract_type=detect_contract_type(title, description),
                )
            )
        return jobs
