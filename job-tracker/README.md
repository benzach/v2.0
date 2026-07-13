# Job Tracker

A free, automated job listing tracker. Scrapes a configurable set of job
sites daily, filters against your criteria, stores results in SQLite, and
emails you a digest of *new* listings only.

## How it works

```
GitHub Actions (daily cron)
        │
        ▼
   main.py orchestrator
        │
   ┌────┴─────┐
   ▼          ▼
scrapers/   config/sites.yaml + search_criteria.yaml
   │
   ▼
core/filters.py  (keyword / location / exclusion matching)
   │
   ▼
core/database.py  (SQLite — dedup via content hash)
   │
   ▼
core/notifier.py  (Gmail SMTP — new jobs only)
```

## Status of the 4 sites you gave me

| Site | Scraper | Status |
|---|---|---|
| CharityJob | `scrapers/static_scraper.py` | ✅ Working — clean server-rendered HTML |
| w4mpjobs | `scrapers/rss_scraper.py` | ✅ Working — uses their official RSS feed, no scraping needed |
| Civil Service Jobs | `scrapers/dynamic_scraper.py` | ⚠️ Stubbed — site shows a bot-check page requiring JS + human interaction. Playwright *might* get through; needs testing on your machine, not guaranteed. |
| Guardian Jobs | `scrapers/dynamic_scraper.py` | ⚠️ Stubbed — actively blocked automated fetches during testing. Needs local Playwright testing; may need stealth plugins or may not be scrapable at all. |

See `config/sites.yaml` for how each is configured.

## Setup (things you need to do)

1. **Create a GitHub repo** and push this code to it.
2. **Gmail App Password**: enable 2FA on your Google account, then generate
   an App Password at https://myaccount.google.com/apppasswords
3. **Add GitHub Secrets** (repo → Settings → Secrets and variables → Actions):
   - `GMAIL_ADDRESS` — the Gmail address to send from
   - `GMAIL_APP_PASSWORD` — the app password from step 2
   - `RECIPIENT_EMAIL` — where digests get sent (can be the same address)
4. **Edit `config/search_criteria.yaml`** with your keywords/locations.
5. **Edit `config/sites.yaml`** to add your remaining ~26 sites as you get
   their URLs (see "Adding a new site" below).
6. Push to `main` — the workflow in `.github/workflows/daily_scan.yml` runs
   every morning automatically, and can also be triggered manually from the
   Actions tab.

## Local development

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install --with-deps chromium   # only needed for dynamic_scraper.py
cp .env.example .env              # fill in your Gmail credentials
python main.py --dry-run          # scrapes + filters but does NOT send email
python main.py                    # full run, sends email if new jobs found
```

## Adding a new site

1. Add an entry to `config/sites.yaml`:
   ```yaml
   - name: "example-site"
     url: "https://example.com/jobs?location=london"
     type: "static"   # or "dynamic" or "rss"
     selectors:
       job_container: "div.job-card"
       title: "h2.job-title"
       link: "a.job-link"
       location: "span.job-location"
   ```
2. If it's `static`, the existing `static_scraper.py` should work with the
   right selectors — no new code needed.
3. If it's `dynamic` (JS-rendered), it uses `dynamic_scraper.py` — same idea,
   Playwright instead of Requests.
4. If it's `rss`, just point `url` at the feed — `rss_scraper.py` handles it
   generically.
5. Run `python main.py --dry-run --site example-site` to test just that one
   site in isolation.

## Project structure

See inline comments in each file. Key ones:
- `main.py` — orchestrator, run this to execute a full cycle
- `core/database.py` — SQLite schema + dedup logic
- `core/filters.py` — matches scraped jobs against your criteria
- `core/notifier.py` — builds and sends the email digest
- `scrapers/base.py` — the contract every scraper follows
- `config/sites.yaml` — the list of sites to scrape
- `config/search_criteria.yaml` — your keywords/locations/exclusions

## What I built vs. what needs your attention

**Built and working:**
- Full database layer with dedup (content-hash based)
- Filter engine
- Email notifier (Gmail SMTP)
- Static scraper framework + working CharityJob scraper
- RSS scraper framework + working w4mpjobs scraper
- GitHub Actions workflow (daily cron + commits DB back to repo)
- Orchestrator with per-site failure isolation (one broken site won't kill the run)
- Dry-run mode for safe testing
- Basic test suite

**Needs your input / action:**
- Push to GitHub + add secrets (I can't do this — no push access)
- Gmail App Password setup
- The remaining ~26 site URLs, so I can build/verify their scrapers
- Local Playwright testing for Civil Service Jobs and Guardian Jobs — I can't
  browser-render JS-heavy or bot-protected sites from here
- robots.txt / ToS check per site before scraping (I'll flag anything
  obviously prohibited as I go, but the call on each site is yours)
- Ongoing selector maintenance when a site's HTML changes
