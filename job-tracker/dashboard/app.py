"""
Phase 2: simple dashboard for monitoring the job database.

Run locally with:
    streamlit run dashboard/app.py

Reads directly from data/jobs.db, so it reflects whatever the most recent
GitHub Actions run committed back to the repo. If you deploy this to
Streamlit Community Cloud, point it at your repo — it'll read jobs.db from
the checked-out copy, so it's only as fresh as the last commit (i.e. once
per day, right after the morning scan).
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.database import JobDatabase  # noqa: E402

st.set_page_config(page_title="Job Tracker Dashboard", layout="wide")
st.title("Job Tracker Dashboard")

DB_PATH = "data/jobs.db"

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

col1, col2, col3 = st.columns(3)
col1.metric("Total jobs tracked", len(df))
col2.metric("Sites covered", df["site"].nunique())
col3.metric("Unnotified (new, pending email)", int((df["notified"] == 0).sum()))

st.divider()

site_filter = st.multiselect("Filter by site", sorted(df["site"].unique()))
if site_filter:
    df = df[df["site"].isin(site_filter)]

search = st.text_input("Search title/organisation")
if search:
    mask = (
        df["title"].str.contains(search, case=False, na=False)
        | df["organisation"].str.contains(search, case=False, na=False)
    )
    df = df[mask]

st.dataframe(
    df[["title", "organisation", "location", "salary", "site", "scraped_at", "url"]]
    .sort_values("scraped_at", ascending=False),
    use_container_width=True,
    column_config={"url": st.column_config.LinkColumn("Apply")},
)

st.divider()
st.subheader("Jobs per site")
st.bar_chart(df["site"].value_counts())
