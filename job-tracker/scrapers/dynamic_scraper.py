"""
Dynamic scraper for JS-rendered or bot-protected sites, using Playwright.

Civil Service Jobs and Guardian Jobs are wired up here but DISABLED by
default in sites.yaml (enabled: false) because both blocked automated
access during testing:

- Civil Service Jobs shows a "Quick check needed" verification page that
  requires JS + a checkbox click before content loads. This may be a
  Cloudflare-style challenge that fingerprints headless browsers, in which
  case Playwright alone won't be enough.
- Guardian Jobs rejected the fetch outright during testing.

Both need local testing with a real (non-headless, or stealth-configured)
browser before they can be trusted to run unattended in GitHub Actions.
Run `python main.py --dry-run --site civil-service-jobs` locally with
`headless=False` (see below) to watch what happens and adjust selectors.
"""
from playwright.sync_api import sync_playwright

from core.models import JobListing
from scrapers.base import BaseScraper

TIMEOUT_MS = 20_000


class DynamicScraper(BaseScraper):
    def scrape(self) -> list[JobListing]:
        selectors = self.config.get("selectors", {})
        container_sel = selectors.get("job_container")
        if not container_sel or container_sel == "TODO":
            raise NotImplementedError(
                f"{self.name} has no working selectors yet — see notes in "
                f"config/sites.yaml. This site needs local Playwright testing "
                f"before it can run unattended."
            )

        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url, timeout=TIMEOUT_MS, wait_until="networkidle")

            # Site-specific pre-scrape steps (e.g. clicking a bot-check
            # checkbox) go here, keyed by site name, before the generic
            # selector extraction below.
            pre_scrape = getattr(self, f"_prepare_{self.name.replace('-', '_')}", None)
            if pre_scrape:
                pre_scrape(page)

            page.wait_for_selector(container_sel, timeout=TIMEOUT_MS)

            for el in page.query_selector_all(container_sel):
                title_el = el.query_selector(selectors["title"]) if selectors.get("title") else el
                link_el = el.query_selector(selectors["link"]) if selectors.get("link") else el
                loc_el = el.query_selector(selectors["location"]) if selectors.get("location") else None

                title = title_el.inner_text().strip() if title_el else ""
                href = link_el.get_attribute("href") if link_el else ""
                location = loc_el.inner_text().strip() if loc_el else ""

                if title and href:
                    if not href.startswith("http"):
                        href = page.url.split("/", 3)[0] + "//" + page.url.split("/", 3)[2] + href
                    jobs.append(
                        JobListing(site=self.name, title=title, url=href, location=location)
                    )

            browser.close()
        return jobs

    def _prepare_civil_service_jobs(self, page):
        """
        TODO: attempt to pass the "Quick check needed" verification page.
        Inspect the checkbox element locally (headless=False) and click it,
        then wait for navigation. Example skeleton:

            checkbox = page.query_selector("input[type=checkbox]")
            if checkbox:
                checkbox.click()
                page.click("text=Continue")
                page.wait_for_load_state("networkidle")

        This is untested — the challenge may be a Cloudflare Turnstile that
        blocks headless browsers regardless. Test locally before relying on it.
        """
        pass
