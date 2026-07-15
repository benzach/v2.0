"""
RSS scraper — for sites that publish an official feed (like w4mpjobs).
Far more reliable than HTML scraping for the listing itself: no selectors
to maintain, no risk of being blocked as a bot.

Verified against w4mpjobs' actual live feed structure:
- Location comes from the RSS <category> element, exposed by feedparser as
  entry.category.
- Organisation comes from the RSS <author> element (often formatted as
  "Name MP (Constituency)" — trailing parenthetical stripped for a
  cleaner org field).
- Salary is only occasionally present in the feed itself — most listings
  only show it on the full JobDetails.aspx page, not the RSS summary.

Because of that last point, this scraper optionally follows each job's
link to fetch its full detail page and pull an accurate salary (and
double-check location/organisation) from there — confirmed working
against real JobDetails.aspx structure. This is opt-in and bounded (see
detail_fetch_limit) since it means one extra HTTP request per job: fine
for a bounded number of the most recent listings, but fetching every
listing every single day would be slow and impolite to the source site
for jobs we've almost certainly already seen and stored.
"""
import html
import re
import time

import feedparser
import requests
from bs4 import BeautifulSoup

from core.models import JobListing
from core.parsing import detect_contract_type
from scrapers.base import BaseScraper

SALARY_PATTERN = re.compile(r"Salary\s*:?\s*([£$]?[\d][\d,\.]*(?:\s*-\s*[£$]?[\d][\d,\.]*)?(?:\s*per\s+\w+)?)", re.IGNORECASE)
ORG_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")

# Detail-page field extraction: labels appear as "Label: value" once the
# page is reduced to plain text. Only searched within the structured
# header block (before the free-text "Job Details" section) to avoid
# false-matching similar words inside the job description body.
DETAIL_LOCATION_PATTERN = re.compile(r"Location\s*:\s*([^\n]+)", re.IGNORECASE)
DETAIL_SALARY_PATTERN = re.compile(r"Salary\s*:\s*([^\n]+)", re.IGNORECASE)
DETAIL_ORG_PATTERN = re.compile(r"Working For\s*:\s*([^\n]+)", re.IGNORECASE)

DETAIL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
DETAIL_TIMEOUT = 15
DETAIL_FETCH_DELAY_SECONDS = 0.5  # be polite — don't hammer the source site


def _clean_description(raw_html: str) -> str:
    """Strips HTML tags and decodes entities (&pound; -> £, etc.) for clean plain text."""
    if not raw_html:
        return ""
    unescaped = html.unescape(raw_html)
    return BeautifulSoup(unescaped, "lxml").get_text(separator=" ", strip=True)


def _extract_salary_from_text(clean_text: str) -> str:
    match = SALARY_PATTERN.search(clean_text)
    return match.group(1).strip() if match else ""


def _clean_organisation(author: str) -> str:
    """Strips a trailing '(Constituency Name)' from MP-style author strings."""
    if not author:
        return ""
    return ORG_TRAILING_PAREN.sub("", author).strip()


def _fetch_job_detail_fields(url: str) -> dict:
    """
    Fetches a job's full detail page and extracts location/salary/org from
    the structured header block. Returns empty strings for any field not
    found — callers should only overwrite existing data with non-empty
    results, since a miss here isn't necessarily a real absence.
    """
    resp = requests.get(url, headers=DETAIL_HEADERS, timeout=DETAIL_TIMEOUT)
    resp.raise_for_status()
    full_text = BeautifulSoup(resp.text, "lxml").get_text(separator="\n")
    # Only search the structured fields block, not the free-text
    # description further down the page.
    header_block = full_text.split("Job Details")[0]

    def _extract(pattern):
        m = pattern.search(header_block)
        return m.group(1).strip() if m else ""

    return {
        "location": _extract(DETAIL_LOCATION_PATTERN),
        "salary": _extract(DETAIL_SALARY_PATTERN),
        "organisation": _extract(DETAIL_ORG_PATTERN),
    }


class RSSScraper(BaseScraper):
    def scrape(self) -> list[JobListing]:
        feed = feedparser.parse(self.url)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse RSS feed for {self.name}: {feed.bozo_exception}")

        # Config-driven: fetch_details enables following each job link for
        # accurate salary; detail_fetch_limit bounds how many of the most
        # recent listings get this treatment per run (feed is newest-first).
        fetch_details = self.config.get("fetch_details", False)
        detail_fetch_limit = self.config.get("detail_fetch_limit", 50)

        jobs = []
        for i, entry in enumerate(feed.entries):
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            posted = entry.get("published", "")

            if not title or not url:
                continue

            description = _clean_description(entry.get("summary", ""))
            location = entry.get("category", "").strip()
            organisation = _clean_organisation(entry.get("author", ""))
            salary = _extract_salary_from_text(description)

            if fetch_details and i < detail_fetch_limit:
                try:
                    detail_fields = _fetch_job_detail_fields(url)
                    # Detail page is authoritative when it has data; feed
                    # data stays as fallback for anything the page misses.
                    location = detail_fields["location"] or location
                    salary = detail_fields["salary"] or salary
                    organisation = detail_fields["organisation"] or organisation
                except Exception as e:
                    # One job's detail page failing shouldn't lose the
                    # whole listing — fall back to whatever the feed gave us.
                    print(f"  (detail fetch failed for {url}: {e})")
                finally:
                    time.sleep(DETAIL_FETCH_DELAY_SECONDS)

            jobs.append(
                JobListing(
                    site=self.name,
                    title=title,
                    url=url,
                    organisation=organisation,
                    location=location,
                    salary=salary,
                    description=description,
                    posted_date=posted,
                    contract_type=detect_contract_type(title, description),
                )
            )
        return jobs
