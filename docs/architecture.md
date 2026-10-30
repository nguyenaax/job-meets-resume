# Architecture

One Python process, one SQLite file, one local dashboard. No queue, no cloud, no daemon. A run is started by hand or by a scheduled shell script and finishes in minutes to an hour depending on how many new postings reach the model.

## Components

| Component | Role |
|---|---|
| Scraper (`job_search.py`, private) | Discovery, gating, fetching, evaluation, persistence. About 2,500 lines. |
| Posting guard (`posting_guard.py`, published) | Integrity gate between fetch and model. |
| Company matcher (`company_match.py`, published) | One shared definition of "same company". |
| Dashboard (`dashboard_server.py` and `dashboard.html`, private) | Local HTTP server on the standard library, one HTML file, the status state machine, notes, ingest by URL, and a form that parks postings found elsewhere. |
| Configuration | A target list (company, ATS, slug, URL, optional per-target search terms and budgets), a `.env` with the API keys, a candidate profile the prompt reads. |

## A run, phase by phase

**Phase 0, pre-matched import.** A spreadsheet of postings that were already matched elsewhere is read through a service account. Those rows skip the model entirely but still go through the deterministic gates, and the sheet's status column can only fill rows the dashboard has not touched; a decision made in the dashboard always wins.

**Phase 1, ATS public APIs.** Each company on the target list is queried through its provider's JSON endpoint: Greenhouse, Lever and Ashby boards; Workday's undocumented career-site API; SmartRecruiters' postings API; Workable and Recruitee, which return descriptions inline. Large boards are swept with search terms rather than pulled whole. Workday and SmartRecruiters need a detail call per description, so each target has a detail budget, and the run asks a callback whether a given job will even be used before spending a call.

**Phase 2, headless browser.** The browser runs only for Workday targets the API could not serve this run. A target served by the API is never scraped a second way.

**Phase 3, search dorks.** Search-engine queries run against public ATS domains and job sites for technical keywords, as the catch-all for companies not on the target list. A hit is kept only when its URL matches the single-posting pattern for that site, so board index pages and other non-posting links are dropped before they cost anything. The title and company are parsed from each site's own result-title format.

**Phases 4 and 5, feeds.** A curated security-jobs feed and a remote-job feed are read next. The remote-job feed carries the description in its payload, so its postings never need a page fetch. The security-jobs feed lists links only, so its postings are fetched by the browser once they pass the gates.

**Phase 6, federal postings.** The run then queries the federal government's job search API, which needs a free key. It asks only for postings open to the public, in a short list of occupational series codes, and searches each term twice: once within a radius of the commute area and once for remote work. The description is assembled from the API's structured fields, and the application closing date is kept as the posting's deadline. A run without the key prints one skip line and moves on.

**Normalize and dedupe.** Tracking parameters and fragments are stripped; a posting seen in this run or already in the database is dropped.

**Gates.** In order: the company ignore list, a non-technical title blocklist, a second title blocklist for tracks the search excludes, and the hold on companies with an application in flight. The first three log a score-1 row so the posting is never fetched again. The hold skips without logging, so those postings resurface by themselves when the application ends. Title blocklists are kept narrow on purpose: a false positive is a permanent row.

**Fetch.** Only now, and only for postings that arrived without a description, does the browser open the page. A JSON-LD `JobPosting` block is preferred when present because it lists every location the rendered page collapses behind "and N more", which was the cause of a class of false commute disqualifications. Bot-challenge pages are detected and the posting is skipped rather than scored on challenge text.

**Posting guard.** Every description, whichever path produced it, passes through the integrity gate before truncation. See `integrity-gate.md`.

**Evaluation.** Each posting gets one model call in JSON mode against a Pydantic schema, with a fallback chain of models behind it. See `evaluation.md`.

**Post-model checks in code.** A disqualifying location forces the score to 1. A commute keyword check on the extracted location catches the case where the model extracted the right place and did not set the flag. A posting the model flagged as requiring a clearance the applicant must already hold is logged as a dealbreaker with a score of 1; a clearance the employer will sponsor after hire passes. A salary floor applies only when the posting states a salary; an estimate never disqualifies.

**Persist.** One row per URL, tagged with the discovery phase that found it, so a report can rank sources by rows, high scores, applications and interviews. Status defaults to NEW. Rows are committed as they are scored.

## Manual ingest

Any URL can be evaluated on demand from the command line. A person already chose the posting, so it skips the ignore list and the title gates, and an application already in flight at that company prints a warning instead of holding the posting. An operator-verified location can be supplied for postings that print one office address while the recruiter has confirmed remote; it is injected into the prompt as trusted input above the untrusted posting, and the row is stamped so a later reader sees why a well-scored row has an onsite address.

## Cost model

The prompt is about 13,500 tokens, of which about 12,000 is a stable prefix (profile, plan, rubric) that the provider caches implicitly when it stays at the front. At the recent rate of about eight model evaluations a day (the first months ran two to three times higher while the target list was being built) that is one to five dollars a month on a Flash-class model. The deterministic gates are what keep it there: in production they have decided 64 percent of postings at zero model cost.

## What a run prints

Each phase reports its count. Each evaluated posting prints its title, company, score, verdict and reasoning. A flagged posting prints the guard's summary and up to three quoted lines. A stopped run says why in one line: quota window, retired model name, or depleted balance.
