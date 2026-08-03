# Upwork Lead Finder

A personal dashboard that watches Upwork saved searches (via RSS — no scraping,
no API approval needed) for high-value SEO/analytics retainer gigs, scores each
posting, and shows them ranked on a free GitHub Pages site. A scheduled GitHub
Action refreshes the data every 6 hours automatically.

## How it works

1. `config/feeds.json` lists Upwork RSS feed URLs (one per saved search) plus
   the keywords used for scoring.
2. `scripts/fetch_leads.py` fetches each feed, scores every job posting, and
   writes the ranked result to `docs/data/leads.json`.
3. `docs/index.html` is a static dashboard that reads that JSON file — filter
   by score, search, or "recurring only".
4. `.github/workflows/update-leads.yml` runs the fetch script on a schedule
   and commits the refreshed data, so the site stays current with zero
   manual work.

## One-time setup

### 1. Get your Upwork RSS feed URLs

For each keyword you want to track ("GA4 Dashboard", "Programmatic SEO",
"SEO Monthly Reporting", "Automated Web Scraper", "Marketing Data Pipeline",
or your own):

1. On Upwork, search jobs with that keyword and any filters you want
   (budget, job type, etc.).
2. Save the search (Upwork calls this a "Saved Search" / job alert).
3. Open **Saved Searches** in your Upwork settings — each saved search has
   an RSS feed link. Copy that URL.

### 2. Fill in `config/feeds.json`

Replace each `PASTE_YOUR_UPWORK_RSS_URL_HERE` with the matching feed URL.
Add or remove entries as needed. You can also tune `high_value_keywords`
and `recurring_keywords` — these drive the scoring.

### 3. Push this repo to GitHub

This repo is already initialized locally. Create an empty repository on
GitHub (no README/license, so it stays empty), then push:

```bash
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

### 4. Turn on GitHub Pages

In the repo on GitHub: **Settings → Pages → Build and deployment → Source:
Deploy from a branch → Branch: `main`, folder: `/docs`**. Save. Your
dashboard will be live at `https://<your-username>.github.io/<repo-name>/`
within a minute or two.

### 5. Let the Action run

The workflow runs automatically every 6 hours. To trigger it immediately:
go to the **Actions** tab → **Update Upwork leads** → **Run workflow**.

## Local testing (optional)

```bash
python scripts/fetch_leads.py
```

This writes `docs/data/leads.json` locally so you can open
`docs/index.html` in a browser and see real data before pushing.

## Ongoing maintenance

Basically none. If Upwork changes its RSS format or a feed URL expires,
re-generate the saved search and swap the URL in `config/feeds.json`.
