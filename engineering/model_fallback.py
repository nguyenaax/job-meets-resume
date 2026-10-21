"""Excerpt: the model fallback chain and its error taxonomy.

One evaluation call walks an ordered list of Gemini models. The interesting part is not
the loop but the three error classes it tells apart, because each one wants a different
response and a scraper that runs unattended cannot ask:

  * quota or rate limit (429, RESOURCE_EXHAUSTED on one model): try the next model;
  * retired model (404, "no longer available"): try the next model, and say so, because
    the fix is editing the chain rather than waiting;
  * billing stop (402, "prepayment credits are depleted"): stop the run at once. Every
    model shares the one prepaid balance, so cascading would only print five misleading
    "quota hit" lines before failing anyway, which is exactly what the first version did.

Rows already evaluated are committed as they go, so a stopped run resumes where it
ended. Model names are examples; the private chain is re-probed before it is edited,
because the provider retires names without notice.
"""

import sys

FALLBACK_CHAIN = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

# Substring matching on the provider's error text. It is deliberately loose: the SDK's
# exception types have changed across versions, and an unmatched error still raises
# rather than being swallowed, so the cost of a loose match is one extra fallback hop.
_QUOTA_SIGNALS = ["429", "quota", "rate limit", "rate_limit", "resource_exhausted",
                  "resourceexhausted", "toomanyrequests", "404", "not found", "not_found"]
_MODEL_GONE_SIGNALS = ["404", "not found", "not_found"]
# Checked before the quota list: nothing in the chain can succeed until the balance is topped up.
_BILLING_SIGNALS = ["402", "prepayment credits", "credits are depleted"]
_BILLING_URL = "https://ai.studio/projects"


def generate_with_fallback(client, contents, config, chain=FALLBACK_CHAIN):
    """Returns the first successful response, or exits the process on a terminal condition.
    `client` is a google-genai Client; `config` carries the JSON mime type and response schema."""
    for i, model in enumerate(chain):
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            if i > 0:
                print(f"  [Fallback] Successfully evaluated using {model}.")
            return response
        except Exception as e:
            err = str(e).lower()
            if any(sig in err for sig in _BILLING_SIGNALS):
                print("\n[!] BILLING STOP: the API key's prepaid balance is depleted (HTTP 402).")
                print(f"[!] Every model answers the same error, so the run stops here. Top up at {_BILLING_URL}")
                print("[!] Evaluated rows are already saved; the next run resumes where this one stopped.")
                sys.exit(1)
            if any(sig in err for sig in _QUOTA_SIGNALS):
                why = "not available" if any(sig in err for sig in _MODEL_GONE_SIGNALS) else "quota hit"
                if i < len(chain) - 1:
                    print(f"  [Fallback] {model} {why}, switching to {chain[i + 1]}.")
                    continue
                print("\n[!] FATAL: every model in the fallback chain failed on quota, rate limit or availability.")
                print("[!] Evaluated rows are already saved. Wait for the quota window, or re-probe the model names.")
                sys.exit(2)   # non-zero so a scheduler sees the run as incomplete
            raise


if __name__ == "__main__":
    # Offline demonstration with a fake client: a retired model, then a quota hit, then success.
    class _Models:
        def __init__(self, script):
            self.script = list(script)

        def generate_content(self, model, contents, config):
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    class _Client:
        def __init__(self, script):
            self.models = _Models(script)

    client = _Client([Exception("404 NOT_FOUND: model no longer available"),
                      Exception("429 RESOURCE_EXHAUSTED: quota exceeded"),
                      "parsed response"])
    print(generate_with_fallback(client, "prompt", {}))
