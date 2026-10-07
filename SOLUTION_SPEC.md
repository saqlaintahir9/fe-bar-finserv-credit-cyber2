# Solution Spec — Real-Time Fraud & Credit-Risk Intelligence Platform

**Industry:** Financial Services — consumer credit card issuer / cloud-native bank
**Customer (synthetic):** *Meridian Bank*
**Issuer scale (synthetic):** large US card issuer — **~$50B** annual card volume, **~40M** authorizations/month
**Divisions in scope:** Credit (Card & Risk Tech) + Cyber (Fraud / Security Operations)
**FE Bar domains targeted:** Product · Industry · Build + AI Mindset · Customer Skills
**Industry Outcome Map (anchor):** Financial Services — **fraud-loss reduction + credit decision quality** (authorization false-positive rate), with SOC analyst productivity as a supporting outcome

> **Data handling:** Every dataset is synthetically generated. PANs are tokenized at generation (`tok_…`). No real customer data, account numbers, or customer-identifying content is in the repo, notebooks, or deck.

**Workspace / repo:** https://github.com/saqlaintahir9/fe-bar-finserv-credit-cyber2 · catalog `fe_bar_meridian` · deck `DECK.md`

---

## 1. The one-liner

> Cyber sees the account-takeover. Credit authorizes the spend. Those signals never meet in the authorization window — so Meridian eats fraud **and** declines good customers. We join them on one governed lakehouse, score in **&lt;50 ms** via Lakebase, attach a structured reason plus a plain-English narrative, and let analysts ask the lake in natural language.

---

## 2. The customer problem (specific, not generic)

A large US card issuer authorizes ~**40M transactions/month** ($50B annual card volume). Two divisions own two halves of the same risk and never share a real-time view:

| Division | Owns | Pain today |
|---|---|---|
| **Cyber (SecOps/Fraud)** | Login/auth events, device fingerprints, ATO detection | Detects a compromised account *minutes-to-hours* after the fraudster has already transacted. Signals sit in a SIEM, not in the authorization path. |
| **Credit (Card & Risk Tech)** | Transaction authorization, credit-line decisions | Scores transactions on transaction features alone. No visibility into whether the account was just taken over. Over-blocks to compensate → high false-positive declines. |

**The gap:** An attacker performs an ATO (Cyber sees the anomalous login), then runs card transactions (Credit authorizes them). Because the two signals never join in the sub-second authorization window, the issuer eats fraud loss *and* declines legitimate customers to compensate.

**Specific, measurable problem statement:**
> *"Fuse Cyber ATO signals and Credit transaction signals into a single real-time risk score,
> served in the authorization path, to reduce net fraud loss and the false-positive decline
> rate simultaneously — with full governance and model explainability for regulators."*

---

## 3. Business outcomes & KPIs (lead with these)

All figures are **illustrative targets** on synthetic data, benchmarked to public industry
ranges — used to frame the value story, not claimed as any real customer's numbers.

**Pilot success (also the deck ask):** 6-week shadow-mode pilot on one card segment — **≥15% fraud-loss reduction with no increase in false-positive declines**, measured on live traffic **before** any decline decision changes.

| KPI | Owner | Baseline (illustrative) | Target | Annualized value |
|---|---|---|---|---|
| **Net fraud loss (bps of volume)** | Credit + Cyber | ~7 bps → $35M/yr | −20% | **~$7.0M avoided** |
| **False-positive decline rate** | Credit | 1 fraud : ~13 false declines | −30% | **~$4–6M recovered revenue + lower attrition** |
| **Authorization decision latency** | Credit (Risk Tech) | 120–300 ms | **&lt;50 ms p99** | protects auth SLA / interchange |
| **ATO mean-time-to-detect (MTTD)** | Cyber | minutes–hours | **&lt;1 s in auth path** | shrinks fraud dwell time |
| **Analyst self-serve ratio** *(supporting, platform)* | Both | ~30% | **&gt;80% via Genie** | **~1.5–2 FTE of analyst/eng time** |
| **Audit-evidence time** | Risk/Compliance | days | **minutes (UC lineage + reason codes)** | exam readiness |
| **UC-governed share of in-scope tables** *(supporting)* | Platform | partial | **100% masked & lineage-tracked** | advances UC adoption |

**Executive framing:** this is a *dual-margin* play — it reduces loss (Cyber/Credit) **and**
grows revenue (fewer good customers declined), while improving regulator and auditor posture.
Lead with **loss bps + FP rate (~$11–13M/yr combined)**; Genie/UC are how, not the headline.

---

## 4. Architecture — the six required stages, integrated

**Unity Catalog:** `fe_bar_meridian`  
**Schemas:** `cyber` · `credit` · `shared_risk`  
**Hot-path contract:** `GET /risk/{account_id}` → `{score, reason_codes[], narrative, model_version, as_of}` from Lakebase (single key lookup). Not a lakehouse SQL query.

```
                        ┌─────────────────── UNITY CATALOG (govern everything) ───────────────────┐
                        │  PII masking · row/column security · lineage · tags · division schemas  │
                        └──────────────────────────────────────────────────────────────────────┘
  SYNTHETIC SOURCES            INGEST (Lakeflow)        INTELLIGENCE (ML + GenAI)      SERVE / CONSUME
  ─────────────────            ─────────────────        ─────────────────────────     ────────────────
  Cyber: auth/login  ─┐         STREAMING / short       ┌─ GBM on fused gold          ┌─ LAKEBASE
   events, devices    │         trigger on auth_events  │   features; MLflow + UC     │   Postgres
                      ├──▶ Lakeflow SDP ──▶ bronze ─────┤   registry                  │   GET /risk/{id}
  Credit: card txns,  │   silver ──▶ gold (fused)        │                             │   <50ms p99
   decisioning        ┘   + expectations                 └─ Structured reason_codes    │
                              (triggered / micro-batch     + GenAI narrative           ├─ GENIE AGENT
                               on transactions)            (analyst English; not       │   NL for SOC +
                                                           the legal adverse-action    │   credit risk
                                                           letter)                     │
                                                                                       └─ DATABRICKS APP
                                                                                           Command Center
```

### Freshness

| Stream | Cadence | Why |
|---|---|---|
| `cyber.auth_events` | **Streaming / short-trigger** Lakeflow | Hottest ATO signals (new device, geo) must land in gold in seconds |
| `credit.card_transactions` | **Triggered micro-batch** | Volume is high; gold features for scoring are precomputed off the hot path |
| Lakebase sync | Continuous / frequent sync from gold + scores | Auth path only does a key lookup |

Feature freshness is **bounded by auth-event pipeline latency**, not by a warehouse query at request time. Heavier 30-day aggregates are precomputed in gold.

### Stage mapping (all six FE Bar stages, no silos)

1. **Lakeflow — ingest.** Lakeflow Spark Declarative Pipeline (`pipelines/fraud_credit_risk.py` + `pipelines/pipeline.yml`): Auto Loader / volume files → bronze → silver (typed, expectations) → gold **fused account-risk feature table** keyed by `account_id` / `txn_id`, joining the latest Cyber signals to each in-flight transaction. Ingest is the Lakeflow pipeline; the notebook inspects it.

2. **Unity Catalog — govern.** Catalog `fe_bar_meridian`, schemas `cyber`, `credit`, `shared_risk`:
   column masking on tokenized PAN / email, row filters so Cyber analysts see security columns and
   Credit analysts see decisioning columns, lineage from bronze → model → serving, and
   governance tags (`pii`, `pci`, `division`). Demonstrates the governance story that lifts
   UC adoption.

3. **Lakebase — operational serving.** Gold features + model score synced to a
   **Lakebase (managed Postgres)** table. The authorization service calls **`GET /risk/{account_id}`**
   — a **single sub-50 ms key lookup** — instead of a lakehouse query.

4. **ML / Gen AI — intelligence.**
   - **ML:** sklearn `GradientBoostingClassifier` (`fused_gbm_v1`) trained on fused Cyber+Credit
     gold columns, tracked in MLflow, registered in UC. Output: fraud/credit-risk probability.
     Gold is the feature table in this version (no separate Feature Store).
   - **Reason codes (deterministic):** velocity, geo-impossible, new-device-within-N-minutes, etc.
     These are what exams and adverse-action processes consume.
   - **GenAI:** `AI_QUERY` turns **those reason codes + feature values** into a **SOC / analyst
     narrative**. It is **not** the Reg B / ECOA adverse-action letter. Letters stay feature- and
     rule-based; GenAI is presentation for humans.

5. **Genie Agent — natural language.** A Genie Space over gold + case tables so
   **SOC analysts** and **credit risk managers** self-serve. Curated metrics, synonyms, sample questions.

6. **Databricks App — surface to the business.** **"Fraud & Credit Risk Command Center"**
   (Streamlit Databricks App): live case queue with fused score + reason codes + GenAI narrative,
   KPI tiles, Cyber vs Credit toggle, embedded Genie panel.

### Demo thread (one account through every stage)

One synthetic account, **`ACC-100042`**, must appear in every stage so the journey is visibly integrated:

1. **Lakeflow:** `cyber.auth_events` — new device + new geo login at T0.
2. **UC:** same row visible; PAN/email masked for the Credit role.
3. **ML:** transaction at T0+4m scores high; reason_codes include `new_device_recent`, `geo_mismatch`.
4. **GenAI:** narrative cites those codes (not a free-hallucinated story).
5. **Lakebase:** `GET /risk/ACC-100042` returns score + codes + `as_of` in &lt;50 ms (timed).
6. **Genie:** “Show ATO-linked cases for ACC-100042” → SQL + rows.
7. **App:** Command Center case queue opens on that account.

Same account id in Lakeflow, UC, scoring, Lakebase, Genie, and the app.

---

## 5. Synthetic data model

Generated by `src/generate_synthetic_data.py` with a seeded RNG and injected fraud patterns
(ATO-then-spend sequences, card-testing bursts, geo-impossible travel) so the ML model has
real signal and the demo tells a story.

**PII rule:** `pan_token` is generated as `tok_` + hex — never a Luhn-valid PAN. Emails are
synthetic (`user{n}@example.invalid`).

**`cyber.auth_events`** — `event_id, account_id, ts, device_id, device_is_new, ip_geo,
geo_is_new, auth_result, failed_attempts_1h, mfa_used, ato_label`

**`credit.card_transactions`** — `txn_id, account_id, ts, amount, mcc, merchant_country,
channel (card-present/ecom), pan_token, decision (approve/decline), fraud_label`

**`credit.accounts`** — `account_id, open_date, credit_limit, segment, home_geo` (synthetic)

**`shared_risk.fused_features` (gold)** — per transaction, joins the latest Cyber signals:
`txn_id, account_id, amount, mcc, minutes_since_new_device_login, geo_mismatch_flag,
failed_logins_1h, txn_velocity_1h, amount_vs_30d_avg, …, risk_score, model_version,
reason_codes`

**`shared_risk.flagged_cases`** — `case_id, txn_id, account_id, risk_score, reason_codes,
reason_narrative (GenAI), analyst_status, division_view`

**Demo fixture:** `ACC-100042` is always injected with a clean ATO-then-spend sequence.

---

## 6. Stage-by-stage build spec + execution evidence

Notebooks are committed with cell output. Query dumps, metrics, and Genie answers live in
`docs/evidence/` as text.

| # | Artifact | What it does | Committed evidence (text) |
|---|---|---|---|
| 0 | `src/generate_synthetic_data.py` | Seeded synthetic Cyber + Credit data, tokenized PAN, injected `ACC-100042` | `docs/evidence/00_data_profile.txt` |
| 1 | `pipelines/fraud_credit_risk.py` + `pipelines/pipeline.yml` + `notebooks/01_lakeflow_pipeline.ipynb` | Lakeflow SDP bronze→silver→gold with expectations; notebook **inspects** the pipeline, does not replace it | executed cells: expectation pass %, gold counts, `ACC-100042` in gold |
| 2 | `notebooks/02_unity_catalog_governance.ipynb` | Masking, row filters, tags, grants | `SHOW GRANTS`, masked-vs-unmasked query output, lineage note |
| 3 | `notebooks/03_train_score_model.ipynb` | Train one GBM, MLflow, UC registry, emit `reason_codes` | ROC-AUC, P/R @ threshold, confusion matrix as text |
| 4 | `notebooks/04_genai_reason_narrative.ipynb` | `AI_QUERY` narratives **conditioned on reason_codes** | 5–10 narratives + the codes they were given |
| 5 | `notebooks/05_lakebase_serving.ipynb` | Sync gold+score; time `GET /risk/ACC-100042` | timed lookup **milliseconds**, sample JSON payload |
| 6 | `docs/genie_space_spec.md` + `docs/evidence/06_genie_qa.txt` | Genie Space; include a question for `ACC-100042` | NL → returned SQL + result rows |
| 7 | `app/app.py` + `app/app.yaml` | Command Center; default case = `ACC-100042` | printed case-queue JSON / table dump as text |

**Build sequence:** generate data → Lakeflow → UC → train/score → GenAI narratives → Lakebase → Genie → App.

---

## 7. Regulatory / compliance mapping (Industry domain strength)

| Requirement | How the build addresses it |
|---|---|
| **Reg B / ECOA (adverse action)** | **Structured `reason_codes` + feature values** are the exam/letter source of truth. GenAI does **not** generate the legal notice. |
| **FCRA** | Decision + feature lineage retained and queryable via UC + case table |
| **SR 11-7 (model risk mgmt)** | MLflow experiment tracking, UC model registry, versioned scores, documented features |
| **BSA/AML** | Fused ATO + transaction signals improve suspicious-activity detection; auditable in Genie |
| **PCI-DSS / GLBA** | Tokenized PAN at source; UC column masking on remaining PII; row-level division separation |
| **Model explainability for exams** | Reason codes + lineage + optional analyst narrative = evidence in minutes |

---

## 8. Risks & trade-offs (be ready to defend these)

- **Latency vs. richness:** Lakebase key-lookup keeps auth &lt;50 ms; heavier features are
  precomputed in gold. Trade-off: feature freshness bounded by **auth-event streaming cadence**
  (seconds), not request-time joins.
- **Model false-negatives:** pair the ML score with **deterministic reason_codes / rules**
  (velocity, geo-impossible) as a safety net — hybrid, not ML-only.
- **PII blast radius:** tokenize at generation; UC masking; Lakebase stores `account_id` +
  scores + codes, not raw PAN.
- **Division data access:** row/column security enforces Credit vs Cyber separation while
  still allowing the *fused* score — governed sharing, not a data free-for-all.
- **LLM fidelity:** narratives are grounded in `reason_codes`; if codes are empty, do not
  generate a story. Cold-start / drift: synthetic data demonstrates the pattern; production
  needs drift monitoring + periodic retrain (Lakeflow + Jobs).

---

## 9. Presentation deck

See `DECK.md` for the business deck (outcome first, then KPIs, then architecture).

## 10. Role-play prep

See `docs/roleplay_prep.md` for the two personas, objections, and altitude switching.
Open on **`ACC-100042`**. Lead with loss bps and FP rate; close technical answers with the business consequence.
