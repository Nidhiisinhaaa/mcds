# Lifestyle Wellness Score & Risk Rules

Everything on this page is plain, deterministic Python (`backend/assessment/scoring.py`
and `backend/assessment/risk_rules.py`) — no LLM is involved in computing a score or a
risk flag. The LLM's job (Phase 3) is only to fill in the underlying `LifestyleProfile`
fields from conversation; scoring and risk detection run entirely on those field values.

A doctor's edits in `LifestyleProfile.doctor_overrides` always take precedence over the
value the LLM extracted, for both the score and the risk rules.

## 1. Wellness Score

Eight lifestyle factors, each weighted, each scored 0–1 ("sub-score") from the patient's
answer, combined into a 0–100 total.

### Weights (sum to 100)

| Factor | Weight |
| --- | --- |
| Sleep | 15 |
| Exercise | 15 |
| Diet | 15 |
| Stress | 15 |
| Smoking | 15 |
| Alcohol | 10 |
| Sitting | 10 |
| Water | 5 |

### Sub-score bands

**Sleep (hours/night)**

| Range | Sub-score |
| --- | --- |
| 7 – 9 | 1.0 |
| 6 to <7, or >9 to 10 | 0.6 |
| 5 to <6 | 0.3 |
| <5 or >10 | 0 |

**Exercise (days/week × minutes/session = weekly minutes)**

| Weekly minutes | Sub-score |
| --- | --- |
| ≥150 | 1.0 |
| 75 – 149 | 0.6 |
| 1 – 74 | 0.3 |
| 0 | 0 |

**Diet pattern**

| Pattern | Sub-score |
| --- | --- |
| Balanced | 1.0 |
| Mixed | 0.6 |
| Irregular | 0.4 |
| Frequent fast food | 0.2 |
| High sugar | 0.2 |

**Stress level**

| Level | Sub-score |
| --- | --- |
| Low | 1.0 |
| Moderate | 0.5 |
| High | 0 |

**Smoking status**

| Status | Sub-score |
| --- | --- |
| None | 1.0 |
| Occasional | 0.3 |
| Daily | 0 |

**Alcohol frequency**

| Frequency | Sub-score |
| --- | --- |
| None | 1.0 |
| Occasional | 0.7 |
| Weekly | 0.4 |
| Daily | 0 |

**Sitting (hours/day)**

| Range | Sub-score |
| --- | --- |
| <6 | 1.0 |
| 6 – 8 | 0.6 |
| >8 to 10 | 0.3 |
| >10 | 0 |

**Water (litres/day)**

| Range | Sub-score |
| --- | --- |
| ≥2 (spec gives 2–3.5 as the top band; treated as open-ended above 2, since more water isn't a risk) | 1.0 |
| 1.5 to <2 | 0.6 |
| 1 to <1.5 | 0.3 |
| <1 | 0 |

### Missing answers

If a slot was never answered (or was skipped after the clarification limit), it is
excluded entirely and the remaining factors' weights are rescaled proportionally back
up to 100. For example, if only "sitting" (weight 10) is missing, the other 7 factors'
weights are each multiplied by 100/90 before being applied. The breakdown lists the
missing factor with `"reason": "not reported"` and weight 0.

### Bands

| Total | Band |
| --- | --- |
| 80 – 100 | Good |
| 60 – 79 | Fair |
| 40 – 59 | Needs attention |
| <40 | Poor |

### Worked example

Patient: sleeps 5 hours; no exercise; frequent fast food; 1 litre of water a day; high
stress; does not smoke; drinks occasionally; sits ~9 hours a day.

| Factor | Value | Sub-score | Weight | Points |
| --- | --- | --- | --- | --- |
| Sleep | 5 h | 0.3 | 15 | 4.5 |
| Exercise | 0 min/week | 0 | 15 | 0 |
| Diet | frequent_fast_food | 0.2 | 15 | 3.0 |
| Stress | high | 0 | 15 | 0 |
| Smoking | none | 1.0 | 15 | 15.0 |
| Alcohol | occasional | 0.7 | 10 | 7.0 |
| Sitting | 9 h | 0.3 | 10 | 3.0 |
| Water | 1 L | 0.3 | 5 | 1.5 |

Total = 4.5 + 0 + 3.0 + 0 + 15.0 + 7.0 + 3.0 + 1.5 = **34 → Poor**

## 2. Risk Flags

`assessment/risk_rules.py`, `evaluate(profile, patient_profile)`. Every flag's `reason`
cites the actual reported value. Composite flags are always phrased as **"possible
risk, for doctor review"** — never a diagnosis.

### Individual rules

| Code | Severity | Trigger |
| --- | --- | --- |
| `poor_sleep` | medium | sleep < 6 hours |
| `sedentary_lifestyle` | medium | weekly exercise < 75 minutes, OR sitting > 8 hours/day |
| `high_stress` | medium | stress level = high |
| `unhealthy_diet` | medium | diet pattern is frequent fast food, high sugar, or irregular |
| `low_water_intake` | low | water < 1.5 L/day |
| `tobacco_use` | high | smoking status is occasional or daily |
| `alcohol_risk` | medium | alcohol frequency is weekly or daily |
| `overweight` | low | BMI ≥ 23 and < 25 (Asian-Indian cutoff) |
| `obese` | medium | BMI ≥ 25 (Asian-Indian cutoff) |

BMI cutoffs are the Asian-Indian thresholds (lower than the WHO global 25/30), and are
configurable constants (`BMI_OVERWEIGHT_CUTOFF`, `BMI_OBESE_CUTOFF`) at the top of
`risk_rules.py`. BMI itself needs the patient's height and weight (`PatientProfile`);
if either is missing, no BMI-based flag fires, but the composite rules below can still
fire from the non-BMI conditions.

### Composite rules

| Code | Severity | Trigger |
| --- | --- | --- |
| `obesity_risk` | medium | BMI ≥ 23, OR (`sedentary_lifestyle` AND `unhealthy_diet`) |
| `hypertension_risk` | high | 2 or more of: high stress, sedentary lifestyle, unhealthy diet, tobacco use, alcohol risk, BMI ≥ 25 |

### Worked example (same patient as above, no height/weight recorded)

- `poor_sleep` — 5 h < 6.
- `sedentary_lifestyle` — 0 weekly exercise minutes < 75 (also: sitting 9 h > 8).
- `high_stress` — stress is high.
- `unhealthy_diet` — frequent fast food.
- `low_water_intake` — 1 L < 1.5 L.
- `tobacco_use` — **not** flagged (smoking = none).
- `alcohol_risk` — **not** flagged (occasional, not weekly/daily).
- `obesity_risk` — BMI unknown, but sedentary_lifestyle AND unhealthy_diet are both
  true → flagged via the composite's second clause.
- `hypertension_risk` — 3 contributing factors present (high_stress, sedentary_lifestyle,
  unhealthy_diet) ≥ 2 → flagged.

Result: `poor_sleep`, `sedentary_lifestyle`, `high_stress`, `unhealthy_diet`,
`low_water_intake`, `obesity_risk`, `hypertension_risk`.
