"""
Filters scraped JobListings against config/search_criteria.yaml.

Kept deliberately simple and rule-based (no fuzzy matching / ML) so behavior
is predictable and easy to debug when a job you expected doesn't show up.
"""
import re
from dataclasses import dataclass

import yaml

from core.models import JobListing


@dataclass
class SearchCriteria:
    keywords: list[str]
    exclude_keywords: list[str]
    locations: list[str]
    min_salary_gbp: int | None
    max_age_days: int | None

    @classmethod
    def from_yaml(cls, path: str = "config/search_criteria.yaml") -> "SearchCriteria":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            keywords=[k.lower() for k in (data.get("keywords") or [])],
            exclude_keywords=[k.lower() for k in (data.get("exclude_keywords") or [])],
            locations=[l.lower() for l in (data.get("locations") or [])],
            min_salary_gbp=data.get("min_salary_gbp"),
            max_age_days=data.get("max_age_days"),
        )


def _extract_salary_number(salary_text: str) -> int | None:
    """Best-effort: pulls the first £ figure out of a salary string."""
    if not salary_text:
        return None
    match = re.search(r"£\s?([\d,]+)", salary_text)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def job_matches(job: JobListing, criteria: SearchCriteria) -> bool:
    haystack = f"{job.title} {job.description}".lower()

    # Keyword match: at least one keyword must appear (if any are configured)
    if criteria.keywords:
        if not any(kw in haystack for kw in criteria.keywords):
            return False

    # Exclusion: none of the exclude keywords may appear
    if any(kw in haystack for kw in criteria.exclude_keywords):
        return False

    # Location filter
    if criteria.locations:
        loc = (job.location or "").lower()
        combined = f"{loc} {haystack}"
        if not any(l in combined for l in criteria.locations):
            return False

    # Salary filter (only applied if we could parse a number; unparsed
    # salaries are kept rather than dropped, per search_criteria.yaml comment)
    if criteria.min_salary_gbp:
        parsed = _extract_salary_number(job.salary)
        if parsed is not None and parsed < criteria.min_salary_gbp:
            return False

    return True


def filter_jobs(jobs: list[JobListing], criteria: SearchCriteria) -> list[JobListing]:
    return [j for j in jobs if job_matches(j, criteria)]
