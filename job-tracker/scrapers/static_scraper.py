"""
Static scraper for server-rendered sites (no JS needed).

Generic selector-driven scraping works for many sites, but some (like
CharityJob) don't cleanly separate title/org/location into distinct CSS
classes on the listing page — so we special-case those with a `parse_*`
method. Add a new `parse_<site_name>` method here for any future static
site that needs custom parsing; otherwise the generic path
(`_generic_scrape`) handles straightforward selector-based sites.
"""
import requests
from bs4 import BeautifulSoup

from core.models import JobListing
from core.parsing import detect_contract_type
from scrapers.base import BaseScraper

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = 15


class StaticScraper(BaseScraper):
    def scrape(self) -> list[JobListing]:
        resp = requests.get(self.url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        parser_method = getattr(self, f"parse_{self.name.replace('-', '_')}", None)
        if parser_method:
            return parser_method(soup)
        return self._generic_scrape(soup)

    def _generic_scrape(self, soup: BeautifulSoup) -> list[JobListing]:
        """Selector-driven scraping for sites configured with plain CSS selectors."""
        selectors = self.config.get("selectors", {})
        container_sel = selectors.get("job_container")
        if not container_sel:
            raise ValueError(f"No job_container selector configured for {self.name}")

        jobs = []
        for el in soup.select(container_sel):
            title_el = el.select_one(selectors["title"]) if selectors.get("title") else el
            link_el = el.select_one(selectors["link"]) if selectors.get("link") else el
            loc_el = el.select_one(selectors["location"]) if selectors.get("location") else None

            title = title_el.get_text(strip=True) if title_el else ""
            href = link_el.get("href", "") if link_el else ""
            if href and not href.startswith("http"):
                href = requests.compat.urljoin(self.url, href)
            location = loc_el.get_text(strip=True) if loc_el else ""

            if title and href:
                jobs.append(
                    JobListing(site=self.name, title=title, url=href, location=location)
                )
        return jobs

    def parse_charityjob(self, soup: BeautifulSoup) -> list[JobListing]:
        """
        CharityJob-specific parsing. Job titles are <h2><a href="/jobs/...">
        which appear twice per listing (a summary card + a full-detail block
        further down the same page) — dedup by URL. Organisation/location
        text sits in the surrounding block but isn't in a stable class name,
        so we grab the nearest text after the link as a best-effort org/location field.
        """
        jobs = []
        seen_urls = set()

        for link in soup.select("h2 a[href*='/jobs/']"):
            href = link.get("href", "")
            if not href:
                continue
            full_url = requests.compat.urljoin(self.url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = link.get_text(strip=True)
            if not title:
                continue

            # org/location/salary/contract-type typically appear in the two
            # or three sibling elements right after the title's containing
            # block (e.g. the <p> tags after the <h2>). We grab a few and
            # scan them for whatever's useful, since exact tag structure
            # per field isn't stable enough to select precisely.
            org_location = ""
            salary = ""
            extra_text_parts = []
            h2 = link.find_parent("h2") or link.find_parent()
            if h2:
                sibling = h2.find_next_sibling()
                count = 0
                while sibling and count < 3:
                    text = sibling.get_text(strip=True)
                    if text:
                        extra_text_parts.append(text)
                        if count == 0:
                            org_location = text
                        elif "£" in text and not salary:
                            salary = text
                    sibling = sibling.find_next_sibling()
                    count += 1

            jobs.append(
                JobListing(
                    site=self.name,
                    title=title,
                    url=full_url,
                    location=org_location,
                    salary=salary,
                    contract_type=detect_contract_type(title, *extra_text_parts),
                )
            )
        return jobs
