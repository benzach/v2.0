"""
Builds and sends the daily digest email via Gmail SMTP.

Requires GMAIL_ADDRESS + GMAIL_APP_PASSWORD (an App Password, not the
regular account password — see README) and RECIPIENT_EMAIL, loaded from
environment variables (see .env.example).
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.models import JobListing

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _build_html(jobs: list[JobListing]) -> str:
    if not jobs:
        return "<p>No new jobs today.</p>"

    rows = []
    for job in jobs:
        rows.append(f"""
        <tr>
          <td style="padding:12px;border-bottom:1px solid #ddd;">
            <a href="{job.url}" style="font-weight:bold;font-size:16px;color:#1a5276;text-decoration:none;">
              {job.title}
            </a><br>
            <span style="color:#555;">{job.organisation} — {job.location}</span><br>
            <span style="color:#2e7d32;">{job.salary}</span><br>
            <span style="color:#888;font-size:12px;">via {job.site}</span>
          </td>
        </tr>
        """)

    return f"""
    <html><body style="font-family:Arial,sans-serif;">
      <h2>{len(jobs)} new job listing(s)</h2>
      <table style="border-collapse:collapse;width:100%;max-width:600px;">
        {''.join(rows)}
      </table>
    </body></html>
    """


def _build_text(jobs: list[JobListing]) -> str:
    if not jobs:
        return "No new jobs today."
    lines = [f"{len(jobs)} new job listing(s):\n"]
    for job in jobs:
        lines.append(f"- {job.title} ({job.organisation}, {job.location})")
        lines.append(f"  {job.salary}" if job.salary else "")
        lines.append(f"  {job.url}\n")
    return "\n".join(lines)


def send_digest(jobs: list[JobListing], dry_run: bool = False) -> bool:
    """
    Sends the digest email. Returns True if sent (or would have been sent,
    in dry-run mode). Does nothing if `jobs` is empty — no point emailing
    "zero new jobs" every day.
    """
    if not jobs:
        print("No new jobs — skipping email.")
        return False

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL", gmail_address)

    if dry_run:
        print(f"[DRY RUN] Would send email with {len(jobs)} new job(s) to {recipient}")
        print(_build_text(jobs))
        return True

    if not gmail_address or not gmail_app_password:
        raise RuntimeError(
            "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set (see .env.example)"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Tracker: {len(jobs)} new listing(s)"
    msg["From"] = gmail_address
    msg["To"] = recipient
    msg.attach(MIMEText(_build_text(jobs), "plain"))
    msg.attach(MIMEText(_build_html(jobs), "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, recipient, msg.as_string())

    print(f"Sent digest with {len(jobs)} new job(s) to {recipient}")
    return True
