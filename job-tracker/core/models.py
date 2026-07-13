"""Shared data model for a scraped job listing."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib


@dataclass
class JobListing:
    site: str                       # e.g. "charityjob" — matches sites.yaml `name`
    title: str
    url: str
    organisation: str = ""
    location: str = ""
    salary: str = ""
    description: str = ""
    posted_date: str = ""           # raw string as scraped; parsing is best-effort
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def content_hash(self) -> str:
        """
        Stable identifier used for dedup. Prefers the URL (usually unique
        per listing); falls back to title+org+site if a site reuses URLs
        or paginates without unique links.
        """
        basis = self.url.strip() or f"{self.site}|{self.title}|{self.organisation}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["content_hash"] = self.content_hash
        return d
