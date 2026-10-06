# Explainable matching and learn → apply

Read `services/matching.py`. No LLM is needed.

## Score

| Factor | Default points | Calculation |
|---|---:|---|
| Skill fit | 30 | Required overlap counts twice; preferred overlap once; unknown list gets neutral 0.5 |
| Role preference | 20 | Exact normalized role family in selected targets |
| Project evidence | 15 | Fraction of requested skills explicitly verified in projects AND present in self-assessed skills |
| Graduation fit | 10 | Published compatible graduation rule gets full factor; unspecified gets 0.5 |
| Location | 10 | First preferred country 1.0; other preferred countries 0.7; otherwise 0 |
| Experience | 5 | Published minimum satisfied 1.0; unspecified 0.5; failed 0 |
| Company preference | 5 | Explicit preference 1.0; otherwise neutral 0.5 |
| Urgency | 5 | Future deadline within 7 days 1.0; later 0.5; unknown/past 0 |

Each factor contributes `weight × fit`; rounded sum yields 0–100. Weights must have exactly all eight keys, remain nonnegative, and sum to 100. A hard rejection or closure overrides the final score to 0 and LOW_PRIORITY; raw factor values stay visible for explanation.

Classification: REVIEW_REQUIRED → WATCH; score ≥65 and no missing required skills → APPLY_NOW; score ≥45 with required gaps → PREP_THEN_APPLY; score ≥35 → WATCH; otherwise LOW_PRIORITY. These are transparent planning heuristics, not a probability of being hired. Graduation scoring is conservative when eligibility reasons mention graduation; review/failure never becomes APPLY_NOW.

Set-based aliases handle a small explicit vocabulary (e.g. postgres/postgresql, js/javascript). We do not claim fuzzy semantic skill equivalence. Self-assessed proficiency >0 counts as exposure. The interface shows missing skills and project evidence so the user can judge readiness beyond the number.

## Learning priorities

Only open, non-disqualified, role-relevant jobs with score ≥35 contribute. For each missing skill:

`weighted_demand = Σ ((2 if required else 1) × job_score/100)`

`priority = 100 × weighted_demand / estimated_learning_hours`

The output includes distinct job count, required count, effort estimate and explanation. Docker's default is 12 hours and Kubernetes 50; unknown topics use 24. These are editable code constants, not research-backed completion promises. Already-known skills do not appear as missing. Required and preferred lists are de-duplicated before aggregation.

Learning progress does not automatically certify a skill. Update the skill's evidence and proficiency after practice. This avoids a checked box turning into an unsupported skill claim.

## Tests and alternatives

Tests exercise exact CGPA boundaries, absent data, blocked ranking, preferred skills, determinism, project evidence, and excluded job demand. An ML ranker could later learn from explicit user feedback, but should never replace hard eligibility. Start with calibrated weights and inspect false positives before considering embeddings or model training.
