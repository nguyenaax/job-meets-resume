# The posting integrity gate

`engineering/posting_guard.py` is the deterministic layer between the fetch and the model. The evaluation prompt also tells the model to treat the posting as data rather than instructions, but a paragraph only works as well as the model obeys it on one particular call. The guard makes the removal mechanical.

The module is adapted from `tools/posting_guard.py` in [ai-job-search](https://github.com/ai-job-search-dev/ai-job-search) (MIT; the notice is in [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)) and rewritten for a pipeline that only scores postings.

## Where it runs

At every point HTML becomes text: the ATS detail fetchers, the inline-description feeds, and both paths of the browser fetch (the JSON-LD description and the rendered page). Always before the 8,000-character truncation, so hidden text at the end of a long page is still seen. The verdict is applied once, after fetch and before the model.

## What it removes

Removal is the defense. None of this reaches the cleaned text:

- Elements hidden by attribute (`hidden`, `aria-hidden="true"`) or by inline style: `display:none`, `visibility:hidden`, zero opacity, zero font size, transparent color, clipping, off-screen positioning.
- `script`, `style`, `noscript`, `svg`, `template`, `iframe`, `object`, and HTML comments.
- Invisible Unicode: the zero-width set, bidirectional controls, soft hyphen, line and paragraph separators, byte-order mark.

Hidden-element text and hidden links are kept aside and scanned, so an instruction inside a hidden block is still found.

## What it flags

Only signals that indicate the text was written for a model:

- Instruction-shaped lines: "ignore previous instructions", "you are an AI evaluator", role prefixes like `Assistant:`, chat-template markers, and the pipeline's own field names and scoring verbs ("set match_score to 10", "rate this candidate", "approve this role").
- Zero-width characters or byte-order marks between two word characters, which is how a phrase is hidden from a human skim while reaching a tokenizer intact. Other invisible characters are removed and counted but do not flag on their own.
- Words that mix Latin letters with Cyrillic or Greek look-alikes.

## What it does not flag

- Hidden blocks and hidden links by themselves. Career pages hide cookie banners, collapsed sections and share widgets on nearly every page; these are reported as context in the findings, not as a verdict.
- The words "ssh", "curl", ".env" and "system prompt". A guard for an agent that runs shell commands would need them; this pipeline only scores, and security postings use those words in their ordinary sense every day.

## What a flag does

The posting is still scored, on the cleaned text. The run prints the summary and up to three quoted lines for the operator. The prompt receives a counts-only block saying hidden content was removed and asking the model to note it in its reasoning; the matched lines are never put back into the prompt, because that would hand the model the text the guard just removed. The row's notes carry a dated stamp, and the dashboard shows a warning tag with the summary on hover.

## Calibration

The self-test holds fixtures for each case: a hidden steering block, a zero-width character inside a word, a clean security posting that mentions SSH, curl, .env files and system-prompt hardening, hidden navigation chrome, JSON-LD markup, a homoglyph, and a visible `Assistant:` line.

Before shipping, the guard ran over 210 live postings from the feeds and public boards the pipeline actually uses. One pattern fired on real copy ("As an AI Transformation Owner" matched "as an AI") and was narrowed to require a following clause word. Two more patterns were dropped before the sweep because they matched ordinary job-ad phrases like "perfect match" and "recommend this job". After that: zero flags on 210 postings, and two rendered career pages came through with their job text intact and only form asterisks and a "No results found" string in the hidden-block report.

## Limit

Hidden-element removal covers inline styles and the hidden attributes. A page that hides text through a CSS class is not caught, because the browser's DOM dump carries no computed styles. Catching that would mean asking the browser for computed visibility per element, which is a cost not yet justified by an observed case.
