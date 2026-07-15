"""
Adzuna API scraper — Tier 1 data source.

Verified against Adzuna's actual documented response schema
(developer.adzuna.com/docs/search). Structured JSON, no HTML parsing
needed — far more reliable than scraping.

Requires ADZUNA_APP_ID and ADZUNA_APP_KEY environment variables.
Register free at https://developer.adzuna.com/signup

Adzuna doesn't have an explicit "graduate" filter like Reed does, so
graduate targeting here relies on keyword search (e.g. what="graduate")
combined with the exclusion list to filter out senior-level false
positives that happen to mention "graduate scheme" in passing.
"""
import os

import requests

from core.models import JobListing
from scrapers.base import BaseScraper

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
TIMEOUT = 15


class AdzunaScraper(BaseScraper):
    def scrape(self) -> list[JobListing]:
        app_id = os.environ.get("ADZUNA_APP_ID")
        app_key = os.environ.get("ADZUNA_APP_KEY")
        if not app_id or not app_key:
            raise RuntimeError(
                "ADZUNA_APP_ID and ADZUNA_APP_KEY must be set as environment "
                "variables (register free at https://developer.adzuna.com/signup)"
            )

        country = self.config.get("country", "gb")
        what = self.config.get("what", "graduate")
        where = self.config.get("where", "")
        results_per_page = self.config.get("results_per_page", 50)
        max_pages = self.config.get("max_pages", 3)

        jobs = []
        for page in range(1, max_pages + 1):
            url = ADZUNA_BASE_URL.format(country=country, page=page)
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": results_per_page,
                "what": what,
                "content-type": "application/json",
            }
            if where:
                params["where"] = where

            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            if not results:
                break  # no more pages

            for item in results:
                jobs.append(self._parse_job(item))

            if len(results) < results_per_page:
                break  # last page

        return jobs

    def _parse_job(self, item: dict) -> JobListing:
        location = item.get("location", {}) or {}
        company = item.get("company", {}) or {}

        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        salary = ""
        if salary_min and salary_max:
            salary = f"£{salary_min:,.0f} - £{salary_max:,.0f}"
        elif salary_min:
            salary = f"£{salary_min:,.0f}+"

        contract_type_parts = []
        if item.get("contract_type"):
            contract_type_parts.append(item["contract_type"].replace("_", " ").title())
        if item.get("contract_time"):
            contract_type_parts.append(item["contract_time"].replace("_", " ").title())

        return JobListing(
            site=self.name,
            title=item.get("title", "").strip(),
            url=item.get("redirect_url", "").strip(),
            organisation=company.get("display_name", ""),
            location=location.get("display_name", ""),
            salary=salary,
            contract_type=", ".join(contract_type_parts),
            description=item.get("description", ""),
            posted_date=item.get("created", ""),
        )
