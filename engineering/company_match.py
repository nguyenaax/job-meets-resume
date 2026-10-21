"""Shared company-name matching for the active-application hold.

Used by BOTH the pipeline (Gate 0c hold in job_search.py) and the dashboard
(auto-pass cascade/revert in dashboard_server.py) so the one-application-per-company
invariant is enforced identically on both surfaces.

Matching is token-based with corporate-suffix stripping and prefix semantics:
  'Acme'      matches 'Acme Ltd' and 'Acme Security'           (prefix / suffix-strip)
  'Nova'      does NOT match 'Supernova' or 'SupernovaML'      (no free substrings)
  'Meta'      does NOT match 'Metabase'
"""
import re

_CORP_SUFFIXES = {"inc", "llc", "ltd", "corp", "co", "company", "corporation", "gmbh", "plc"}
_PLACEHOLDERS = {(), ("unknown",), ("unknown", "company")}


def company_tokens(name):
    """Normalizes a company name to a tuple of lowercase tokens with trailing
    corporate suffixes removed. 'Acme Ltd.' -> ('acme',)."""
    toks = [t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if t]
    while len(toks) > 1 and toks[-1] in _CORP_SUFFIXES:
        toks.pop()
    return tuple(toks)


def is_placeholder(tokens):
    """True for empty/'Unknown'/'Unknown Company': these never match anything."""
    return tokens in _PLACEHOLDERS


def companies_match(tokens_a, tokens_b):
    """True when one token tuple equals or is a token-prefix of the other.
    ('acme',) matches ('acme','security'); ('nova',) does NOT match ('supernovaml',)."""
    if not tokens_a or not tokens_b:
        return False
    n = min(len(tokens_a), len(tokens_b))
    return tokens_a[:n] == tokens_b[:n]
