"""
Reed.co.uk API scraper — Tier 1 data source.

Verified against a real Reed API response (exact field names confirmed:
jobId, employerName, jobTitle, locationName, minimumSalary, maximumSalary,
jobDescription, jobUrl, etc.) — not guessed from prose documentation.

Requires REED_API_KEY environment variable. Register free at
https://www.reed.co.uk/developers/jobseeker

Reed has a built-in `graduate=true` search parameter — genuinely useful
for graduate-targeted sourcing, unlike Adzuna which relies on keyword
matching alone.

Auth: API key goes in HTTP Basic Auth as the username, password left blank.
"""
import os

import requests

from core.models import JobListing
from scrapers.base import BaseScraper

REED_SEARCH_URL = "https://www.reed.co.uk/api/1.0/search"
TIMEOUT = 15


class ReedScraper(BaseScraper):
    def scrape(self) -> list[JobListing]:
        api_key = os.environ.get("REED_API_KEY")
        if not api_key:
            raise RuntimeError(
                "REED_API_KEY must be set as an environment variable "
                "(register free at https://www.reed.co.uk/developers/jobseeker)"
            )

        params = {
            "keywords": self.config.get("keywords", ""),
            "locationName": self.config.get("locationName", ""),
            "graduate": "true" if self.config.get("graduate_only", True) else "false",
            "resultsToTake": self.config.get("results_to_take", 100),
        }
        # Strip empty params — Reed treats an empty string differently from omitted
        params = {k: v for k, v in params.items() if v not in ("", None)}

        resp = requests.get(REED_SEARCH_URL, params=params, auth=(api_key, ""), timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("results", []):
            jobs.append(self._parse_job(item))
        return jobs

    def _parse_job(self, item: dict) -> JobListing:
        salary_min = item.get("minimumSalary")
        salary_max = item.get("maximumSalary")
        currency = item.get("currency", "GBP")
        symbol = "£" if currency == "GBP" else currency + " "

        salary = ""
        if salary_min and salary_max:
            salary = f"{symbol}{salary_min:,.0f} - {symbol}{salary_max:,.0f}"
        elif salary_min:
            salary = f"{symbol}{salary_min:,.0f}+"

        contract_type_parts = []
        if item.get("contractType"):
            contract_type_parts.append(str(item["contractType"]).title())
        if item.get("fullTime"):
            contract_type_parts.append("Full-time")
        if item.get("partTime"):
            contract_type_parts.append("Part-time")

        return JobListing(
            site=self.name,
            title=item.get("jobTitle", "").strip(),
            url=item.get("jobUrl", "").strip(),
            organisation=item.get("employerName", "") or "",
            location=item.get("locationName", "") or "",
            salary=salary,
            contract_type=", ".join(contract_type_parts),
            description=item.get("jobDescription", "") or "",
            posted_date=item.get("date", "") or "",
        )
