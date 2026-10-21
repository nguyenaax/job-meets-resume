"""Excerpt: the Workday career-site client, the most awkward of the seven ATS integrations.

Greenhouse, Lever and Ashby publish documented JSON boards. Workday does not: each
tenant's career site is a single-page app backed by an undocumented, unversioned JSON
API at /wday/cxs/{tenant}/{site}/jobs. Three things make it fiddly, and each has a
specific answer here:

  * The site id in the public URL is not always the site id the API wants. Tenants
    rename it freely, and a wrong id answers 404 or 422, never an empty list, so the
    client probes a short candidate list and prints the working id so it can be pinned
    in configuration.
  * The list endpoint caps `limit` at 20 and returns no description, so descriptions
    come from a per-job detail call. A per-target detail budget keeps a 2,000-posting
    board from turning into 2,000 requests, and the caller decides which jobs are worth
    a detail fetch (not already evaluated, title passes the cheap gates) before any
    network call is spent.
  * Vanity career domains that are not Workday answer 200 with an HTML shell. The
    request wrapper checks the content type and fails loudly rather than parsing an
    empty board.

The matching helpers for the other providers follow the same contract and are omitted.

Trust boundary: hosts come from the operator's own target configuration, so this client
does not run the SSRF guard that the browser fetch path uses (see url_safety.py), follows
redirects, and does not cap response size. Posting paths come from the provider's JSON
and are appended to the configured host, never used as full URLs.
"""

import re
import time
from urllib.parse import urlparse

import requests

_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; job-pipeline/1.0)",
}
_WORKDAY_PAGE_LIMIT = 20       # the cxs API answers HTTP 400 to anything larger
_DEFAULT_MAX_PAGES = 5
_DEFAULT_MAX_DETAILS = 25      # per target, per run
_SITE_CANDIDATES = ["External", "External_Career_Site", "Careers", "careers",
                    "External_Careers", "ExternalCareers"]


def request_json(method, url, *, json_body=None, params=None, timeout=15, attempts=3):
    """requests wrapper with a timeout retry and a content-type guard."""
    for attempt in range(attempts):
        try:
            r = requests.request(method, url, json=json_body, params=params,
                                 headers=_HEADERS, timeout=timeout)
            r.raise_for_status()
            break
        except requests.exceptions.Timeout:
            if attempt < attempts - 1:
                time.sleep(2)
            else:
                raise
    ctype = r.headers.get("content-type", "")
    if "json" not in ctype.lower():
        raise ValueError(f"expected JSON, got '{ctype or 'unknown'}' from {url}")
    return r.json()


def workday_config(target):
    """Resolves {host, tenant, site} from a target's URL unless both are pinned.
    Returns None for hosts that are not Workday tenants, which routes the target to the
    browser-based fallback instead."""
    parsed = urlparse(target.get("url") or "")
    host = parsed.hostname or ""
    tenant, site = target.get("tenant"), target.get("site")
    if not tenant:
        if not host.endswith(".myworkdayjobs.com"):
            return None
        tenant = host.split(".")[0]
    if not site:
        parts = [p for p in parsed.path.split("/") if p]
        if parts and re.fullmatch(r"[a-z]{2}[-_][A-Za-z]{2}", parts[0]):
            parts = parts[1:]      # drop a leading locale segment such as en-US
        site = parts[0] if parts else None
    if not (host and tenant and site):
        return None
    return {"host": f"{parsed.scheme or 'https'}://{host}", "tenant": tenant, "site": site}


def resolve_site(cfg):
    """Confirms the site id answers, probing the candidate list if it does not."""
    tried = []
    for site in [cfg["site"]] + [c for c in _SITE_CANDIDATES if c != cfg["site"]]:
        url = f"{cfg['host']}/wday/cxs/{cfg['tenant']}/{site}/jobs"
        try:
            data = request_json("POST", url, json_body={"appliedFacets": {}, "limit": 1,
                                                       "offset": 0, "searchText": ""},
                                timeout=15, attempts=1)
        except Exception as e:
            tried.append(f"{site}: {str(e)[:60]}")
            time.sleep(0.4)
            continue
        if isinstance(data, dict) and "jobPostings" in data:
            if site != cfg["site"]:
                print(f"     site '{cfg['site']}' rejected; using '{site}' (pin it in config to skip this probe)")
            cfg["site"] = site
            return cfg
        tried.append(f"{site}: 200 but no jobPostings key")
        time.sleep(0.4)
    raise ValueError("no working Workday site id; tried " + "; ".join(tried))


def fetch_workday_target(target, searches, need_description=None,
                         max_pages=_DEFAULT_MAX_PAGES, max_details=_DEFAULT_MAX_DETAILS,
                         to_text=lambda html: html):
    """Lists postings for each search term, then fetches descriptions within the budget.

    `need_description(job) -> bool` lets the caller skip detail fetches for jobs the run
    would discard anyway. `to_text` is the HTML cleaner (the posting integrity gate in
    the full pipeline)."""
    cfg = resolve_site(workday_config(target))
    base = f"{cfg['host']}/wday/cxs/{cfg['tenant']}/{cfg['site']}"
    discovered, seen, budget = [], set(), max_details
    for term in searches:
        for page in range(max_pages):
            data = request_json("POST", f"{base}/jobs", json_body={
                "appliedFacets": {}, "limit": _WORKDAY_PAGE_LIMIT,
                "offset": page * _WORKDAY_PAGE_LIMIT, "searchText": term})
            postings = data.get("jobPostings") or []
            for p in postings:
                path = p.get("externalPath") or ""
                if not path or path in seen:
                    continue
                seen.add(path)
                job = {"url": f"{cfg['host']}/en-US/{cfg['site']}{path}",
                       "title": p.get("title") or "Unknown",
                       "company": target.get("company", "Unknown"),
                       "location": p.get("locationsText") or "Unknown"}
                if budget > 0 and (need_description is None or need_description(job)):
                    budget -= 1
                    try:
                        info = request_json("GET", f"{base}{path}").get("jobPostingInfo") or {}
                    except Exception as e:
                        print(f"  [!] detail fetch failed for '{job['title']}': {e}")
                        info = {}
                    text = to_text(info.get("jobDescription") or "")
                    if len(text) > 300:
                        job["description"] = text[:8000]
                    time.sleep(0.3)
                discovered.append(job)
            if len(postings) < _WORKDAY_PAGE_LIMIT:
                break
    print(f"  Workday/{cfg['tenant']}:{cfg['site']}: {len(discovered)} jobs "
          f"({max_details - budget} descriptions fetched)")
    return discovered
