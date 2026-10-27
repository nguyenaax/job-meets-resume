# Evaluation

The model is asked one question per posting: how well does this posting fit this candidate, and why. Everything about how that question is asked is designed to make the answer checkable.

## Inputs

- The candidate's resume, a longer master record of experience, and an in-flight upskilling plan, all as text in a stable prefix.
- The posting: title, company and the cleaned description, wrapped in explicit delimiters and labelled as untrusted data.
- Optionally, an operator-verified location (manual ingest only), labelled as trusted and placed above the posting.
- Optionally, the posting guard's one-line verdict for a flagged posting, counts only, never the quoted lines.

## The rubric, in outline

The prompt is private, but its shape is ordinary and worth stating.

1. Required versus preferred. A missing preferred qualification is never a gate failure and never a dealbreaker.
2. Binary gates in strict order: role level and track, technical core alignment, location, and a dealbreaker gap check. The first failure ends scoring at a capped value.
3. A scoring band per verdict, so a score and a verdict cannot disagree.
4. Gap typing by time to close: covered by the plan, closable in an hour or two of reading, or weeks of hands-on work.
5. Salary: quote what the posting states; estimate only when it states nothing, and flag the estimate.

## The contract

`engineering/schema.py` is the response schema. The design decisions:

- **Verdict labels are a closed set**, and two of them were split after use showed they were different findings: "Overqualified" (the role is on the candidate's track but scoped below them) and "Misaligned" (the daily work is a different discipline). Track decides whether to pursue; level only decides how to frame it.
- **Gaps are typed by time**, which is what makes them actionable downstream.
- **Estimates are quarantined.** An estimated salary goes in its own fields with `salary_is_estimated` set, so it can be shown to the reader without ever passing for a stated one.
- **Disqualifiers are booleans, so code never parses prose.** `clearance_required` stays free text for the reader, and `active_clearance_required` is a separate flag for the one case that disqualifies: a clearance the applicant must already hold. A clearance the employer sponsors after hire, or one a posting only prefers, leaves the flag false.
- **Context fields never score.** Company stage is recorded for the reader and the prompt says so.

## After the model

Code checks four things the model might have gotten wrong:

- If the model set the disqualifying-location flag, the score is forced to 1 regardless of what it wrote.
- If it did not, a keyword check on the extracted location catches the extracted-but-unflagged case. This was added after real rows scored well against an onsite posting in the wrong city.
- If the model set the active-clearance flag, the row is logged as a dealbreaker with a score of 1, whatever fit score it gave the work itself.
- If the posting states a maximum salary below the floor, the row is logged as salary-disqualified. Estimates never reach this check.

## Model selection

The fallback chain is made of Flash-class models, ordered by a small blind comparison: each candidate model re-scored postings the operator had already decided on, and the model whose scores tracked those decisions best went first. The comparison also caught a wording trap the previous model fell into, where two jobs that share nouns but not verbs were being scored as the same work. A vulnerability researcher finds bugs in code and a vulnerability intelligence analyst tracks the ones already disclosed, yet both postings are full of exploits, patches and proofs of concept. A second provider's models ranked the postings the same way on a shifted scale and would have needed their own cutoff; the chain stayed with the cheaper provider.

## Known limits

- One call per posting, no self-consistency sampling. Scores on the same posting can move a point between runs.
- The prompt still occasionally admits an engineering role the gate should fail. The fix is a prompt change that has been deferred.
- Scores are a triage signal for a human, not a decision. The dashboard exists because the operator makes the call.
