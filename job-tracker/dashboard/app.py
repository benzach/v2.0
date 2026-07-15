"""
Job Tracker Dashboard — Phase 2.

Reads directly from data/jobs.db and lets you filter live across every
job ever scraped (not just ones that matched your saved email criteria).

Run locally with:
    streamlit run dashboard/app.py

Deployed on Streamlit Community Cloud, this reflects whatever the most
recent GitHub Actions run committed back to the repo — i.e. it's as fresh
as this morning's scan, refreshed once a day.

No login is required yet (single-user use case). If this gets rolled out
to other people later, add authentication here — Streamlit supports simple
password gating via st.secrets, or a full auth provider for real accounts.
Keeping this file read-only (no write actions against the DB) means
exposing it publicly today is low-risk even without auth.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.database import JobDatabase  # noqa: E402

st.set_page_config(page_title="Job Tracker Dashboard", layout="wide")
st.title("Job Tracker Dashboard")

DB_PATH = str(Path(__file__).parent.parent / "data" / "jobs.db")

if not Path(DB_PATH).exists():
    st.warning(
        f"No database found at {DB_PATH} yet. Run `python main.py` at least "
        f"once to populate it."
    )
    st.stop()

db = JobDatabase(DB_PATH)
rows = db.get_all_jobs()

if not rows:
    st.info("Database exists but has no jobs saved yet.")
    st.stop()

df = pd.DataFrame([dict(r) for r in rows])

# Defensive: if the DB hasn't been migrated to the latest schema yet
# (e.g. core/database.py update hasn't been deployed), fill in sensible
# defaults for newer columns instead of crashing the whole dashboard.
missing_cols = [c for c in ["contract_type", "matched_criteria"] if c not in [k for k in dict(rows[0]).keys()]]
if missing_cols:
    st.warning(
        f"Your database is missing column(s): {', '.join(missing_cols)}. "
        f"This means core/database.py on GitHub hasn't been updated to the "
        f"latest version yet (it should auto-migrate the DB on next load "
        f"once it is). Filters relying on these fields won't be accurate "
        f"until then."
    )

for col, default in [
    ("contract_type", ""),
    ("matched_criteria", 0),
    ("notified", 0),
    ("salary", ""),
    ("organisation", ""),
    ("location", ""),
    ("description", ""),
]:
    if col not in df.columns:
        df[col] = default

# Some jobs (especially older ones scraped before certain fields existed)
# have NULL values in the database, which pandas silently converts to NaN
# (a float) rather than empty text. Text operations like membership checks
# or .str.contains() then crash because you can't run those against a
# float. Force all text columns to actual strings so filters below never
# have to deal with NaN.
text_cols = ["title", "organisation", "location", "salary", "contract_type", "description", "url", "site"]
for col in text_cols:
    if col in df.columns:
        df[col] = df[col].fillna("").astype(str)

df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")

with st.expander("Debug info (temporary — for troubleshooting)"):
    st.write("Columns in loaded data:", list(df.columns))
    st.write("Row count:", len(df))

# --- Top-line metrics ---------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total jobs tracked", len(df))
col2.metric("Sites covered", df["site"].nunique())
col3.metric("Matched your saved criteria", int((df["matched_criteria"] == 1).sum()))
col4.metric("Pending email (new, unnotified)", int((df["notified"] == 0).sum()))

st.divider()

# --- Filters --------------------------------------------------------------
st.subheader("Filters")
f1, f2, f3 = st.columns(3)

with f1:
    site_filter = st.multiselect("Site", sorted(df["site"].unique()))
    keyword = st.text_input("Keyword (title / organisation / description)")

with f2:
    location_query = st.text_input("Location contains")
    # Contract type values are stored as comma-joined strings (e.g.
    # "Full-time, Permanent") since a job can have more than one tag —
    # build the option list by splitting all of them apart.
    all_contract_tags = sorted(
        {
            tag.strip()
            for val in df["contract_type"].dropna()
            for tag in val.split(",")
            if tag.strip()
        }
    )
    contract_filter = st.multiselect("Contract type", all_contract_tags)

with f3:
    min_salary = st.number_input("Minimum salary (£, approximate)", min_value=0, value=0, step=1000)
    only_matched = st.checkbox("Only show jobs matching saved search criteria", value=False)

filtered = df.copy()

# Guards against a pandas quirk: boolean-indexing a DataFrame that has
# already been narrowed to zero rows can silently drop ALL columns as a
# side effect (confirmed locally — happens once any filter above returns
# no matches, e.g. filtering by location when a site never populates that
# field). Restoring the expected columns after every step prevents that
# from cascading into a crash on a later filter or the final display.
EXPECTED_COLUMNS = list(df.columns)


def _restore_columns(frame):
    for col in EXPECTED_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    return frame


if site_filter:
    filtered = _restore_columns(filtered[filtered["site"].isin(site_filter)])

if keyword:
    kw = keyword.lower()
    mask = (
        filtered["title"].str.lower().str.contains(kw, na=False)
        | filtered["organisation"].str.lower().str.contains(kw, na=False)
        | filtered["description"].str.lower().str.contains(kw, na=False)
    )
    filtered = _restore_columns(filtered[mask])

if location_query:
    filtered = _restore_columns(
        filtered[filtered["location"].str.lower().str.contains(location_query.lower(), na=False)]
    )

if contract_filter:
    filtered = _restore_columns(
        filtered[
            filtered["contract_type"].apply(
                lambda v: any(tag in v for tag in contract_filter)
            )
        ]
    )

if min_salary:
    # Best-effort: pull first £ figure out of the salary string.
    def extract_salary(s):
        import re
        if not s:
            return None
        m = re.search(r"£\s?([\d,]+)", s)
        return int(m.group(1).replace(",", "")) if m else None

    filtered["_parsed_salary"] = filtered["salary"].apply(extract_salary)
    # Keep unparsed salaries too, same "don't silently drop" philosophy as
    # the email filter — only exclude if we successfully parsed a LOWER number.
    filtered = _restore_columns(
        filtered[
            filtered["_parsed_salary"].isna() | (filtered["_parsed_salary"] >= min_salary)
        ]
    )
    filtered = filtered.drop(columns=["_parsed_salary"], errors="ignore")

if only_matched:
    filtered = _restore_columns(filtered[filtered["matched_criteria"] == 1])

st.divider()
st.subheader(f"{len(filtered)} listing(s)")

# Final belt-and-suspenders: guarantee every column the display needs
# exists, no matter what happened above.
DISPLAY_COLUMNS = [
    "title", "organisation", "location", "salary", "contract_type",
    "site", "matched_criteria", "scraped_at", "url",
]
for col in DISPLAY_COLUMNS:
    if col not in filtered.columns:
        filtered[col] = pd.NA

st.dataframe(
    filtered[DISPLAY_COLUMNS].sort_values("scraped_at", ascending=False),
    use_container_width=True,
    hide_index=True,
    column_config={
        "url": st.column_config.LinkColumn("Apply"),
        "matched_criteria": st.column_config.CheckboxColumn("In digest?"),
        "scraped_at": st.column_config.DatetimeColumn("Scraped", format="D MMM YYYY, HH:mm"),
    },
)

st.divider()
st.subheader("Jobs per site")
st.bar_chart(filtered["site"].value_counts())
