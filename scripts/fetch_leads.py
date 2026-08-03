"""
Pulls Upwork saved-search RSS feeds (configured in config/feeds.json), scores each
job posting for fit against SEO/analytics retainer work, and writes the merged,
ranked result to docs/data/leads.json for the static dashboard to read.

Uses only the Python standard library so it runs anywhere (including GitHub
Actions' default runner) with no pip installs.
"""
import json
import hashlib
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "feeds.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "leads.json"
MAX_LEADS = 300
USER_AGENT = "Mozilla/5.0 (compatible; upwork-lead-finder/1.0)"

BUDGET_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_feed(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = strip_html(item.findtext("description") or "")
        items.append({
            "guid": guid,
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "snippet": description[:400],
        })
    return items


def extract_budget(snippet):
    amounts = BUDGET_RE.findall(snippet)
    if not amounts:
        return None
    values = [float(a.replace("$", "").replace(",", "")) for a in amounts]
    return max(values)


def score_item(title, snippet, feed_name, cfg):
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


def make_id(guid):
    return hashlib.sha1(guid.encode("utf-8")).hexdigest()[:16]


def load_existing():
    if OUTPUT_PATH.exists():
        try:
            data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            return {lead["id"]: lead for lead in data.get("leads", [])}
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def main():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    existing = load_existing()
    now = datetime.now(timezone.utc).isoformat()

    merged = dict(existing)
    errors = []

    for feed in cfg["feeds"]:
        url = feed.get("url", "")
        if not url or "PASTE_YOUR" in url:
            continue
        try:
            items = fetch_feed(url)
        except Exception as exc:
            errors.append(f"{feed['name']}: {exc}")
            continue

        for item in items:
            lead_id = make_id(item["guid"])
            score, is_recurring, budget, matched = score_item(
                item["title"], item["snippet"], feed["name"], cfg
            )
            first_seen = merged.get(lead_id, {}).get("first_seen", now)
            merged[lead_id] = {
                "id": lead_id,
                "source_feed": feed["name"],
                "title": item["title"],
                "link": item["link"],
                "pub_date": item["pub_date"],
                "snippet": item["snippet"],
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
        print("Feed errors:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
