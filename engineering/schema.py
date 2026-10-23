"""Excerpt: the structured-output contract the evaluator enforces on every LLM call.

The private pipeline passes this Pydantic model as the response schema on a JSON-mode
Gemini request, so the model cannot answer in prose and every row written to SQLite
has the same shape. The field descriptions are the only prompt the schema carries; the
evaluation rubric itself (gates, scoring bands, candidate constraints) lives in a
withheld prompt builder. Candidate-specific wording has been generalized here.

Three design points worth noticing:

  * Gaps are typed by how long they take to close, not by subject. That is what lets a
    deterministic post-processing step treat a "just in time" gap and a "significant
    training" gap differently, and what makes the dashboard's gap lists useful.
  * Salary estimates are display-only and flagged. A guessed number can never trip the
    salary gate; only a salary the posting states can.
  * A disqualifier the code acts on is a boolean, not a phrase to parse. The clearance
    text is kept for the reader; the check in code reads active_clearance_required.
"""

from typing import Optional

from pydantic import BaseModel, Field

VERDICTS = (
    "Strong Match", "Viable Pivot", "Stretch Role", "Lateral Move",
    "Overqualified", "Misaligned", "High Risk / Skill Gap", "Logistical Dealbreaker",
)


class SkillGaps(BaseModel):
    roadmap_gaps: list[str] = Field(
        default_factory=list,
        description="Gaps already covered by the candidate's in-flight upskilling plan. "
                    "Bridgeable in a compressed pre-interview window; never dealbreakers.")
    just_in_time_gaps: list[str] = Field(
        default_factory=list,
        description="Niche tools, frameworks, standards or domain terminology the candidate "
                    "can internalize in one to two hours of focused reading.")
    significant_training_gaps: list[str] = Field(
        default_factory=list,
        description="Deep architectural concepts, entire languages or engineering disciplines "
                    "absent from the resume that need weeks of hands-on work.")
    is_dealbreaker: bool = Field(
        description="True if significant_training_gaps so outweigh the candidate's core "
                    "capabilities that the role's primary requirements cannot be met. "
                    "Caps match_score at 4.")


class JobEvaluation(BaseModel):
    true_location: str = Field(
        description="The geographic requirement extracted strictly from the posting body, "
                    "ignoring ATS headers. Example: 'Remote - US', 'Hybrid - Austin, TX'.")
    match_score: int = Field(ge=1, le=10, description="Score 1 to 10. Geo-disqualified roles score 1.")
    geo_disqualified: bool = Field(
        description="True if the role mandates in-office or hybrid presence outside the "
                    "candidate's configured commute area. Forces match_score 1.")
    reasoning: str = Field(description="Two or three sentences justifying the score and any gate failures.")
    is_worth_applying: bool = Field(description="True only if match_score >= 8 and not geo_disqualified.")
    fit_verdict: str = Field(
        default="",
        description="Exactly one of: " + ", ".join(f"'{v}'" for v in VERDICTS) + ". "
                    "'Overqualified' is a level finding (role scoped below the candidate on "
                    "their own track); 'Misaligned' is a track finding (a different discipline). "
                    "When both apply, use 'Misaligned'.")
    company_stage: str = Field(
        default="Unknown",
        description="Exactly one of 'Startup', 'Growth-stage', 'Established', 'Unknown'. "
                    "Context only; never affects scoring.")
    salary_min: Optional[int] = Field(description="Minimum base salary stated in the posting. Null if absent.")
    salary_max: Optional[int] = Field(description="Maximum base salary stated in the posting. Null if absent.")
    estimated_salary_min: Optional[int] = Field(
        default=None,
        description="Display-only estimate, provided only when the posting states no salary.")
    estimated_salary_max: Optional[int] = Field(
        default=None,
        description="Display-only estimate, provided only when the posting states no salary.")
    salary_is_estimated: bool = Field(
        default=False,
        description="True only when the estimate fields were filled. Never affects match_score.")
    clearance_required: str = Field(description="Security clearance required, or 'None'.")
    active_clearance_required: bool = Field(
        default=False,
        description="True only when the applicant must already hold an active or current "
                    "clearance to apply or start. False when it can be obtained after hire, "
                    "is only preferred, or is absent. A True value is a dealbreaker in code.")
    tech_stack: str = Field(description="Comma-separated primary tools and languages, or 'None'.")
    skill_gaps: SkillGaps


if __name__ == "__main__":
    import json
    print(json.dumps(JobEvaluation.model_json_schema(), indent=2)[:1200] + "\n...")
