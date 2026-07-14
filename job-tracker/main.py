"""
Orchestrator: scrape all enabled sites -> save ALL of them to the DB ->
determine which are new -> filter those against saved criteria -> email a
digest of what's new AND matches.

As of the dashboard update, every scraped job gets saved (not just ones
matching search_criteria.yaml) so the dashboard can filter across
everything live. Only new jobs that also match criteria trigger an email.

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

    all_new_and_matched = []
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

        # Save EVERYTHING scraped (dedup handles repeats) so the dashboard
        # has the full picture, regardless of your current search criteria.
        new_jobs = db.save_new_jobs(jobs)
        print(f"  -> {len(new_jobs)} are new (not seen before)")

        # Of the new ones, figure out which match your saved criteria —
        # that subset is what's email-worthy.
        matched = filter_jobs(new_jobs, criteria)
        db.mark_matched(matched)
        print(f"  -> {len(matched)} of those match search criteria")

        all_new_and_matched.extend(matched)

    print(f"\nTotal new + matching jobs across all sites: {len(all_new_and_matched)}")
    if failures:
        print(f"Sites that failed this run: {', '.join(failures)}", file=sys.stderr)

    if all_new_and_matched:
        sent = send_digest(all_new_and_matched, dry_run=dry_run)
        if sent and not dry_run:
            db.mark_notified(all_new_and_matched)

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
