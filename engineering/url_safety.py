"""Excerpt: URL hygiene for a scraper that stores what it fetches and renders it later.

Two guards sit between discovery and fetch:

  * clean_url normalizes a posting URL so the same job found by three sources counts
    once, and refuses non-web schemes. The scheme check matters because stored URLs are
    rendered as links in a local dashboard: a javascript: or data: URL that slipped in
    from a feed would become a stored XSS sink.
  * is_safe_fetch_url is an SSRF guard. Discovery sources include public feeds and search
    results, so a URL can point anywhere. Only http(s) to publicly routable hosts is
    fetched, and the check resolves the hostname so a DNS name pointing at loopback,
    a private range or a cloud metadata address is caught as well.
"""

import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = {"source", "trk", "refid", "trackingid", "ref"}


def clean_url(url: str) -> str:
    """Strips tracking parameters and fragments; returns '' for non-http(s) URLs."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ""
        qs = parse_qsl(parsed.query)
        kept = [(k, v) for k, v in qs
                if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS]
        return urlunparse(parsed._replace(query=urlencode(kept), fragment=""))
    except Exception:
        return ""   # fail closed: a URL that cannot be parsed is not stored


def is_safe_fetch_url(url: str) -> bool:
    """True only for http(s) URLs whose host resolves exclusively to globally routable
    addresses.

    Scope, stated honestly: the check resolves once, before the fetch, and the browser
    resolves again when it connects. A host that changes its answer between the two
    (DNS rebinding) or a redirect to an internal address is not caught. For a scraper
    that opens public careers pages found through feeds and search results, the threat
    this closes is the common one: a planted link straight at loopback, a private range
    or a cloud metadata address. Pinning the vetted address for the fetch would close
    the rest and is the next step if a case ever warrants it.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        infos = socket.getaddrinfo(parsed.hostname, None)
        if not infos:
            return False
        for info in infos:
            addr = ipaddress.ip_address(info[4][0])
            if not addr.is_global:
                return False
        return True
    except Exception:
        return False


if __name__ == "__main__":
    print(clean_url("https://boards.greenhouse.io/acme/jobs/123?gh_jid=123&utm_source=x&ref=y#app"))
    print(clean_url("javascript:alert(1)") == "")
    print(is_safe_fetch_url("http://127.0.0.1/admin"), is_safe_fetch_url("http://169.254.169.254/"))
