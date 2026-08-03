"""
Reads Upwork saved-search job-alert emails over IMAP (Upwork retired RSS feeds
in August 2024), scores each job posting found in those emails for fit against
SEO/analytics retainer work, and writes the merged, ranked result to
docs/data/leads.json for the static dashboard to read.

Uses only the Python standard library so it runs anywhere (including GitHub
Actions' default runner) with no pip installs.

Credentials are read from environment variables (set as GitHub Actions
secrets, never committed):
  IMAP_HOST      e.g. imap.gmail.com (default)
  IMAP_USER      the mailbox address that receives Upwork alert emails
  IMAP_PASSWORD  an app password for that mailbox (not your normal password)
"""
import email
import hashlib
import html
import imaplib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "feeds.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "leads.json"
MAX_LEADS = 300

BUDGET_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")
ANCHOR_RE = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
PLAIN_LINK_RE = re.compile(r"https?://\S*upwork\.com\S*", re.IGNORECASE)


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_budget(snippet):
    amounts = BUDGET_RE.findall(snippet)
    if not amounts:
        return None
    values = [float(a.replace("$", "").replace(",", "")) for a in amounts]
    return max(values)


def score_item(title, snippet, cfg):
    text = f"{title} {snippet}".lower()
    score = 0
    matched_keywords = []

    for kw in cfg["high_value_keywords"]:
        if kw.lower() in text:
            score += 10
            matched_keywords.append(kw)

    is_recurring = any(kw.lower() in text for kw in cfg["recurring_keywords"])
    if is_recurring:
        score += 20

    budget = extract_budget(snippet)
    if budget:
        score += min(budget / 50, 30)

    return round(score, 1), is_recurring, budget, matched_keywords


def make_id(link):
    parts = urlsplit(link)
    key = f"{parts.netloc}{parts.path}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def get_body_parts(msg):
    html_body, text_body = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get_content_disposition() == "attachment":
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                continue
            if ctype == "text/html":
                html_body += decoded
            elif ctype == "text/plain":
                text_body += decoded
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace") if payload else ""
        except Exception:
            decoded = ""
        if msg.get_content_type() == "text/html":
            html_body = decoded
        else:
            text_body = decoded
    return html_body, text_body


def parse_jobs_from_email(html_body, text_body):
    jobs = []
    if html_body:
        matches = list(ANCHOR_RE.finditer(html_body))
        for i, m in enumerate(matches):
            href = html.unescape(m.group(1))
            if "upwork.com" not in href or "/jobs/" not in href:
                continue
            title = strip_html(m.group(2))
            if not title:
                continue
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else min(len(html_body), start + 600)
            snippet = strip_html(html_body[start:end])[:400]
            jobs.append({"link": href, "title": title, "snippet": snippet})

    if not jobs and text_body:
        lines = text_body.splitlines()
        for i, line in enumerate(lines):
            for link in PLAIN_LINK_RE.findall(line):
                title_line = next((l.strip() for l in lines[max(0, i - 2):i] if l.strip()), "Upwork job alert")
                jobs.append({"link": link.strip(), "title": title_line, "snippet": line.strip()[:400]})

    return jobs


def load_existing():
    if OUTPUT_PATH.exists():
        try:
            data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            return {lead["id"]: lead for lead in data.get("leads", [])}
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def fetch_upwork_emails(cfg):
    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    user = os.environ.get("IMAP_USER")
    password = os.environ.get("IMAP_PASSWORD")
    if not user or not password:
        print("IMAP_USER / IMAP_PASSWORD not set - skipping email fetch (no leads to add this run).")
        return []

    since_days = cfg.get("email_search", {}).get("since_days", 4)
    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%d-%b-%Y")
    from_contains = cfg.get("email_search", {}).get("from_contains", "upwork.com")

    messages = []
    conn = imaplib.IMAP4_SSL(host)
    try:
        conn.login(user, password)
        conn.select("INBOX", readonly=True)
        status, data = conn.search(None, f'(FROM "{from_contains}" SINCE "{since_date}")')
        if status != "OK":
            return []
        ids = data[0].split()
        for msg_id in ids:
            status, msg_data = conn.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            messages.append(msg)
    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()

    return messages


def main():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    existing = load_existing()
    now = datetime.now(timezone.utc).isoformat()
    merged = dict(existing)
    errors = []

    try:
        messages = fetch_upwork_emails(cfg)
    except Exception as exc:
        messages = []
        errors.append(f"IMAP fetch failed: {exc}")

    for msg in messages:
        try:
            pub_date = parsedate_to_datetime(msg.get("Date")).isoformat()
        except Exception:
            pub_date = now

        html_body, text_body = get_body_parts(msg)
        for job in parse_jobs_from_email(html_body, text_body):
            lead_id = make_id(job["link"])
            score, is_recurring, budget, matched = score_item(job["title"], job["snippet"], cfg)
            first_seen = merged.get(lead_id, {}).get("first_seen", now)
            merged[lead_id] = {
                "id": lead_id,
                "source_feed": "Upwork email alert",
                "title": job["title"],
                "link": job["link"],
                "pub_date": pub_date,
                "snippet": job["snippet"],
                "score": score,
                "is_recurring": is_recurring,
                "budget_hint": budget,
                "matched_keywords": matched,
                "first_seen": first_seen,
            }

    def sort_key(lead):
        return (-lead["score"], lead.get("pub_date") or "")

    leads = sorted(merged.values(), key=sort_key)[:MAX_LEADS]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({
            "generated_at": now,
            "errors": errors,
            "leads": leads,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(leads)} leads to {OUTPUT_PATH}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
