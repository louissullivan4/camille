# Test Data Corpus — Phase 0

This directory contains all test data for Camille development and demo.
Do not commit real documents containing PII or proprietary information.

---

## Structure

```
test_data/
├── real_documents/          # Actual public governance docs (download manually)
│   ├── DOWNLOAD_CHECKLIST.md   ← START HERE for real docs
│   ├── model_cards/
│   ├── bias_audits/
│   ├── frameworks/
│   └── incidents/
│
├── company_a_greenscore/    # Persona 1: LOW risk  (target score 78–90)
├── company_b_quickhire/     # Persona 2: MEDIUM risk (target score 40–60)
├── company_c_autoclaim/     # Persona 3: HIGH/CRITICAL risk (target score 8–28)
│
└── expected_outputs/        # Ground truth JSON for automated validation
    ├── company_a_expected_score.json
    ├── company_b_expected_score.json
    └── company_c_expected_score.json
```

---

## The Three Personas

### GreenScore AI — Low Risk (target: 78–90)
Fintech ESG scoring company. 200 employees. Dedicated AI governance team.
3 models: ESG classifier, portfolio optimizer, risk predictor. NIST RMF aligned.
**Why it scores well:** Complete model inventory, quarterly bias audits, AI-specific IR plan,
board-level ethics committee, DPIA completed.
**Demo use:** Shows the system correctly recognizing well-governed AI.

### QuickHire Inc — Medium Risk (target: 40–60)
HR Tech resume screening. 85 employees. No dedicated governance role.
2 models + ChatGPT API. Stale model card, LL144 non-compliant, active EEOC complaint.
**Why it scores poorly:** No IR plan, 3-year-old bias audit, HITL for VP+ only, no model inventory.
**Demo use:** Primary demo persona. Shows system catching real, specific governance gaps.
See: `docs/manual_walkthrough_quickhire.md` for the underwriter's full analysis.

### AutoClaim Pro — High/Critical Risk (target: 8–28)
Insurtech auto-claims adjudication. 150 employees. CTO "owns AI."
5+ models including auto-denial engine. 2 active lawsuits, 1 AG inquiry.
**Why it scores critically:** Auto-denies claims without human review, zero bias testing,
no governance docs, active litigation.
**Demo use:** Shows system flagging severe risk and recommending decline.

---

## File Formats

Synthetic documents are `.txt` files with realistic governance document content.
Convert to PDF before Phase 1 integration testing using any tool (e.g., Pandoc, browser print).

Real documents should be `.pdf` files placed in `real_documents/` subdirectories.
See `real_documents/DOWNLOAD_CHECKLIST.md` for what to download and where.

---

## Automated Validation

After each pipeline run, compare actual output against `expected_outputs/*.json`.
The JSON files specify:
- `expected_overall_score`: `{min, max}` — output must fall in this range
- `expected_risk_tier`: exact string match
- `expected_dimension_scores`: per-dimension range + key flags that must be detected
- `expected_critical_flags`: list of flags the extraction MUST produce
- `validation_notes`: human-readable explanation of what correct behavior looks like

A pipeline run is considered **passing** when:
1. Overall score falls within `expected_overall_score` range
2. Risk tier matches exactly
3. All `expected_critical_flags` are present in extraction output
4. Per-dimension scores fall within their ranges

---

## Day 4 Manual Walkthrough

`docs/manual_walkthrough_quickhire.md` contains a full manual underwriter assessment of
QuickHire Inc — reading notes, dimension-by-dimension scoring, judgment calls, and
recommended coverage conditions. This document is the **spec** for:
- Extraction prompt design (what to look for, how to frame findings)
- Scoring rule calibration (what each flag is worth)
- Dimension score expected ranges
- Demo script for showing the system to MGA customers
