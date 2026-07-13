"""
Orchestrator: scrape all enabled sites -> filter -> save new jobs to DB ->
email a digest of what's new.

Usage:
    python main.py                          # full run
    python main.py --dry-run                # scrape+filter+save, but don't send email
    python main.py --site charityjob         # run only one site (ignores enabled flag)
    python main.py --site charityjob --dry-run

Failure isolation: if one site's scraper throws, it's logged and skipped —
the run continues with the remaining sites rather than aborting entirely.
"""
import argparse
import os
import sys
import traceback

from dotenv import load_dotenv

from core.database import JobDatabase
from core.filters import SearchCriteria, filter_jobs
from core.notifier import send_digest
from scrapers.registry import load_site_configs, build_scrapers


def run(dry_run: bool = False, only_site: str | None = None) -> int:
    load_dotenv()

    db_path = os.environ.get("DATABASE_PATH", "data/jobs.db")
    db = JobDatabase(db_path)
    criteria = SearchCriteria.from_yaml("config/search_criteria.yaml")

    site_configs = load_site_configs("config/sites.yaml")
    scrapers = build_scrapers(site_configs, only_site=only_site)

    if not scrapers:
        print("No enabled scrapers found (check config/sites.yaml).", file=sys.stderr)
        return 1

    all_new_jobs = []
    failures = []

    for scraper in scrapers:
        print(f"Scraping {scraper.name}...")
        try:
            jobs = scraper.scrape()
            print(f"  -> found {len(jobs)} listing(s)")
        except Exception as e:
            print(f"  -> FAILED: {e}", file=sys.stderr)
            traceback.print_exc()
            failures.append(scraper.name)
            continue

        matched = filter_jobs(jobs, criteria)
        print(f"  -> {len(matched)} matched search criteria")

        new_jobs = db.save_new_jobs(matched)
        print(f"  -> {len(new_jobs)} are new (not seen before)")
        all_new_jobs.extend(new_jobs)

    print(f"\nTotal new jobs across all sites: {len(all_new_jobs)}")
    if failures:
        print(f"Sites that failed this run: {', '.join(failures)}", file=sys.stderr)

    if all_new_jobs:
        sent = send_digest(all_new_jobs, dry_run=dry_run)
        if sent and not dry_run:
            db.mark_notified(all_new_jobs)

    # Non-zero exit if every single site failed (signals a real problem to
    # GitHub Actions), but not if only some failed (partial success is fine).
    if failures and len(failures) == len(scrapers):
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Tracker orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Don't send email")
    parser.add_argument("--site", default=None, help="Run only this site (by name)")
    args = parser.parse_args()

    sys.exit(run(dry_run=args.dry_run, only_site=args.site))
