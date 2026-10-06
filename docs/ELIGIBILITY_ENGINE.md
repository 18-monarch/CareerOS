# Eligibility engine

Read `apps/api/careeros/services/eligibility.py` alongside `tests/test_domain.py`.

Evaluation precedes recommendation ranking. Hard facts come from the validated profile and job requirements. AI cannot override them.

| State | Meaning |
|---|---|
| CLOSED | Inactive, deadline passed or explicit expiry passed |
| NOT_ELIGIBLE | At least one confirmed hard requirement fails |
| REVIEW_REQUIRED | Profile facts missing, extracted hard facts unconfirmed, language unresolved, or work authorization uncertain |
| LIKELY_ELIGIBLE | No conflicting rule found, but no published structured hard checks to confirm |
| ELIGIBLE | All available structured hard checks pass and no review blockers remain |

Order: closure → graduation → CGPA → degree/branch → experience range → work authorization → unresolved language → aggregate state. A failure takes precedence over review. Reasons show both the requirement and the candidate value. Missing preferred skills never disqualify a candidate; required skill gaps affect preparation rather than silently becoming an academic/authorization rejection.

Examples for the seed profile: minimum CGPA 8.0 fails against 7.38; 7.38 passes exactly; allowed graduation [2027] fails 2028; an explicit Netherlands work-authorization requirement fails when only India is recorded. Sponsorship availability does not magically satisfy a requirement for existing authorization.

`provenance[field] = {method, confidence, source_text, confirmed}` distinguishes rule/AI extraction from confirmed facts. Unconfirmed extracted hard requirements request review even with a high confidence score. Campus save asks the user to verify and marks reviewed fields manual/confirmed. Imported requirements retain uncertainty.

The local CGPA profile uses a 0–10 scale. The parser is intentionally conservative and requires review; do not compare a foreign 4-point GPA directly. Review degree synonyms that are not in the small explicit normalization map. Country notes are not legal determinations.

Complexity: fixed number of hard checks plus O(Y + D + B + A) membership inputs for allowed years, degree/branch lists and authorizations. Space is proportional to the explanations returned. Every invocation is deterministic for the same inputs and `now`; inject `now` in boundary tests.
