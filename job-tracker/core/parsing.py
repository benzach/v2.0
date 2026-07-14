"""
Small shared parsing helpers used by multiple scrapers.

Sites rarely expose contract type (full-time/part-time/remote/etc.) in a
clean, separate field — it's usually just sitting in surrounding text.
Rather than write brittle site-specific selectors for it, we scan whatever
text is available (title, description, surrounding blurb) for known terms.
This is best-effort: a job with none of these words present just gets an
empty contract_type, which is fine — the dashboard filter simply won't
match it against a specific contract type, but it still shows up
unfiltered.
"""
import re

# Order matters for display but not for matching — checked independently.
CONTRACT_TYPE_TERMS = [
    "Full-time",
    "Part-time",
    "Permanent",
    "Contract",
    "Temporary",
    "Internship",
    "Remote",
    "Hybrid",
    "On-site",
]


def detect_contract_type(*text_fragments: str) -> str:
    """
    Scans the given text fragments for known contract-type terms and
    returns a comma-separated string of whichever ones were found
    (e.g. "Full-time, Permanent"). Case-insensitive matching, but the
    canonical casing from CONTRACT_TYPE_TERMS is used in the output.
    """
    combined = " ".join(f for f in text_fragments if f).lower()
    if not combined:
        return ""

    found = []
    for term in CONTRACT_TYPE_TERMS:
        # word-boundary match so "Contract" doesn't match inside "Contractor"
        if re.search(rf"\b{re.escape(term.lower())}\b", combined):
            found.append(term)
    return ", ".join(found)
