# Upwork Lead Finder

A personal dashboard that watches Upwork saved-search job-alert emails for
high-value SEO/analytics retainer gigs, scores each posting, and shows them
ranked on a free GitHub Pages site. A scheduled GitHub Action refreshes the
data automatically — Upwork retired RSS feeds in August 2024, so email
alerts are the remaining official (ToS-safe) channel for automation.

## How it works

1. You save a job search on Upwork with your target keywords/filters, with
   email alerts on.
2. `scripts/fetch_leads.py` connects to a mailbox over IMAP, reads recent
   Upwork alert emails, extracts each job posting, scores it, and writes the
   ranked result to `docs/data/leads.json`.
3. `docs/index.html` is a static dashboard that reads that JSON file — filter
   by score, search, or "recurring only".
4. `.github/workflows/update-leads.yml` runs the fetch script on a schedule
   and commits the refreshed data, so the site stays current with zero
   manual work.

This is a passive alert dashboard only — it never auto-applies or
auto-bids on jobs. (Upwork killed RSS specifically because bots were using
it to auto-bid with spam proposals; staying read-only keeps this tool on
the right side of that.)

## One-time setup

### 1. Confirm your saved search is generating email alerts

You've already saved a search on Upwork with retainer-oriented keywords.
Upwork batches alert emails every 20 minutes to 2 hours — check your inbox
after saving to confirm they're arriving, and look in the saved search's own
settings (next to it in your saved-searches list) for a frequency toggle if
you don't see any within an hour or two.

### 2. Set up the mailbox the script will read

You want a dedicated Gmail for this rather than mixing it into your main
inbox. Since Upwork only emails whatever address is already on your Upwork
account, do this:

1. **Create the new Gmail** yourself at [accounts.google.com](https://accounts.google.com)
   (this is an account-creation step only you can do).
2. **In your existing Gmail** (the one Upwork actually emails), set up
   auto-forwarding for Upwork's mail only:
   - Settings (gear icon) → **See all settings** → **Forwarding and POP/IMAP**
     → **Add a forwarding address** → enter the new Gmail → verify it (Google
     emails a confirmation code to the new account).
   - Then go to **Settings → Filters and Blocked Addresses → Create a new
     filter** → From: `upwork.com` → **Create filter** → check **Forward it
     to** and pick the new address.
3. **On the new dedicated Gmail**, enable **2-Step Verification**
   (Google Account → Security), then create an **App Password**
   (Google Account → Security → App passwords → app: "Mail" → generate).
   Copy the 16-character password — you'll paste it directly into GitHub in
   the next step, not here in chat.

### 3. Add GitHub repo secrets (never commit these)

In the repo on GitHub: **Settings → Secrets and variables → Actions → New
repository secret**, add:

- `IMAP_USER` — the new dedicated Gmail address
- `IMAP_PASSWORD` — the app password from step 2

### 4. Tune `config/feeds.json` (optional)

`high_value_keywords` and `recurring_keywords` drive the scoring — add or
adjust terms to match how you phrase your saved searches.

### 5. Push this repo to GitHub

Already done for this repo — future changes just need `git push`.

### 6. Turn on GitHub Pages

In the repo on GitHub: **Settings → Pages → Build and deployment → Source:
Deploy from a branch → Branch: `main`, folder: `/docs`**. Save. Your
dashboard will be live at `https://baek82.github.io/Upwork-Lead-Finder/`
within a minute or two.

### 7. Let the Action run

The workflow runs automatically every 6 hours. To trigger it immediately:
go to the **Actions** tab → **Update Upwork leads** → **Run workflow**.

## Local testing (optional)

```bash
IMAP_USER="you@gmail.com" IMAP_PASSWORD="app-password" python scripts/fetch_leads.py
```

This writes `docs/data/leads.json` locally so you can open
`docs/index.html` in a browser and see real data before pushing. Without
those environment variables set, the script just writes an empty result
instead of failing.

## If email parsing misses jobs

The parser looks for `<a href="...upwork.com/jobs/...">` links in the HTML
alert email and grabs the surrounding text as the snippet. If Upwork's
email template doesn't match that pattern well, paste the raw HTML source
of one alert email (in Gmail: open the email → "⋮" menu → **Show original**)
so the regex in `scripts/fetch_leads.py` can be tuned to it.

## Ongoing maintenance

Basically none. If Upwork changes its email format, or you want to track
different keywords, adjust the saved search on Upwork and/or
`config/feeds.json`.
