# The status model

Every row carries one status, changed only through the dashboard's API. The statuses and the transitions between them encode the rules of a job search so the operator does not have to remember them.

## Statuses

| Status | Meaning |
|---|---|
| NEW | Scored, no decision yet |
| PARKED | Set aside to come back to, such as a role with a tailored resume not yet sent; not an application |
| PASS | Operator declined |
| MISMATCH | Scored wrong; hidden from the default view and kept for prompt review |
| APPLIED | Application submitted; stamps the applied date |
| INTERVIEW | At least one conversation held |
| OFFER | Offer received |
| REJECTED | Turned down before any conversation |
| REJECTED_INTERVIEW | Turned down after at least one interview |

The two rejection statuses exist because they answer different questions when the operator reviews what is working. Both end the application.

PARKED is a bookmark, not an application. It stamps no applied date, starts no auto-pass cascade and does not hold the company at the scraper's gate, and the cascade only touches NEW rows, so a parked role survives an application to a sibling role. A parked row stays visible whatever its score. A form in the dashboard parks a posting the pipeline never found, as a row with no model score.

## The auto-pass cascade

When a row at a company first enters APPLIED, INTERVIEW or OFFER, every NEW row at the same company is set to PASS and tagged with a marker in its notes. The rule is one application per company at a time, and the cascade enforces it without the operator having to find the siblings.

The cascade is edge-triggered: it fires on the transition into an active status, not on every save, so re-clicking APPLIED does not re-run it.

## The revert

When no application at that company is still active (the last active row moved to a rejection, or was passed), every row that carries the marker goes back to NEW and loses the marker. Those roles are live again and the operator sees them again. A row the operator set by hand never carries the marker, so it is never reverted; a status set deliberately stays set.

## The pipeline side of the same rule

The scraper's hold gate skips new postings at companies with an active application, without logging a row. That is deliberate: a logged score-1 row would never be fetched again, while a skipped posting flows through normally on the first run after the application ends. The hold and the cascade share one company matcher (`engineering/company_match.py`), so "the same company" means the same thing on both surfaces.

## Why a matcher at all

Company names arrive from seven ATS providers, two feeds and a search engine, and they do not agree. The matcher normalizes to lowercase tokens, strips trailing corporate suffixes, and matches on token prefix. "Acme" matches "Acme Ltd" and "Acme Security". "Nova" does not match "Supernova", because free substring matching produced exactly that kind of false positive on real board data. Placeholders like "Unknown Company" never match anything.

## Dates

The applied date is stamped the first time a row enters an application-stage status from outside that set, and kept on later moves within the set, so a contact never drifts to a different week because of a later click. A mis-click reverted to NEW and re-applied gets a fresh date.
