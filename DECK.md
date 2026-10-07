# Business Presentation — Real-Time Fraud & Credit-Risk Intelligence

**Audience:** Executive sponsor (business) + Domain owner (technical/data lead)
**Customer (synthetic):** Meridian Bank — large US card issuer (~$50B volume, ~40M auths/month)
Lead with the outcome, quantify in the buyer's KPIs, then show how.

---

### Slide 1 — Title
**Stop paying twice: cut fraud loss AND stop declining good customers**
Real-Time Fraud & Credit-Risk Intelligence on Databricks
*A unified Cyber + Credit decisioning platform*

Speaker note: "We're going to fix a problem that costs you money two ways at once."

---

### Slide 2 — The business problem (outcome-first)
Meridian loses money at the moment of authorization — **twice**:
- **Fraud slips through** → ~$35M/yr net fraud loss (≈7 bps of $50B volume)
- **Good customers get declined** → ~13 false declines per 1 real fraud → lost revenue + attrition

Root cause: **Cyber** knows the account was just taken over, but **Credit** authorizes the
transaction without that signal. The two never meet in the sub-second auth window.

---

### Slide 3 — What we built (one line)
> Cyber sees the ATO; Credit authorizes the spend. We **fuse those signals**, score in
> **<50 ms** (Lakebase `GET /risk/{account_id}`), attach **reason codes** plus an analyst
> narrative, and let SOC / credit risk **ask in natural language**.

---

### Slide 4 — The business outcomes

| KPI | Today | With the platform | Value |
|---|---|---|---|
| Net fraud loss | ~$35M/yr | **−20%** | **~$7.0M avoided** |
| False-positive declines | 1:13 | **−30%** | **~$4–6M revenue recovered** |
| Auth decision latency | 120–300 ms | **<50 ms p99** | protects auth SLA |
| ATO mean-time-to-detect | minutes–hours | **<1 s (in auth path)** | shrinks dwell time |
| Analyst self-serve *(supporting)* | ~30% | **>80% (Genie)** | **~1.5–2 FTE freed** |
| Audit-evidence time | days | **minutes** | exam-ready |

**Headline:** a dual-margin play — **~$11–13M/yr** combined loss-avoided + revenue-recovered.
Genie and UC are *how*; loss bps and FP rate are *what the buyer funds*.

---

### Slide 5 — How it works (architecture, 1 diagram)
Lakeflow (stream auth events, micro-batch txns) → Unity Catalog (mask/lineage) → ML score
+ **structured reason_codes** + GenAI analyst narrative → Lakebase (`GET /risk/ACC-100042`)
→ Genie → Databricks App. Gold *is* the feature table (no separate Feature Store in v1).

Speaker note for technical stakeholder: "Everything is governed by Unity Catalog end to end,
and the hot path is a single Lakebase key lookup, not a lakehouse query."

---

### Slide 6 — Demo: Fraud & Credit Risk Command Center
- **Tell:** "I'll follow one account, **ACC-100042**, from a new-device login to an e-com spend four minutes later."
- **Show:** Command Center → **model risk score 0.90**, version `fused_gbm_v1`, top features
  (amount, minutes since new-device login, failed logins, geo mismatch, ATO signal) →
  reason_codes (`new_device_recent`, `geo_mismatch`) → analyst narrative grounded in those
  codes → Genie: “Show ATO-linked cases for ACC-100042.”
- **Tell:** "That's a fraud loss avoided. The same fused signal is what lets us *stop over-declining* good customers."

---

### Slide 7 — Why Databricks (platform value)
- One platform, one copy of governed data — Cyber and Credit on the same lakehouse
- Real-time serving (Lakebase) without a separate OLTP stack to run
- ML + GenAI + NL analytics native, not bolted on
- Governance (UC) and explainability built in → regulator-ready

---

### Slide 8 — For the technical stakeholder (altitude switch)
- **Data quality:** Lakeflow expectations gate bronze→silver→gold
- **Security:** UC column masking (PAN/SSN), row-level division separation, full lineage
- **Latency:** precomputed gold features synced to Lakebase; <50 ms p99 key lookup
- **Model risk:** MLflow + UC registry (SR 11-7); hybrid ML + deterministic **reason_codes** (not LLM-as-letter)
- **Integration:** auth service calls Lakebase; no change to card rails

---

### Slide 9 — Compliance & risk
Reg B/ECOA: **reason_codes + features** are the adverse-action source of truth; GenAI is
SOC/analyst narrative only. FCRA lineage · SR 11-7 · BSA/AML uplift · PCI/GLBA (tokenized
PAN + UC masking). Audit evidence in minutes, not days.

---

### Slide 10 — Rollout & time-to-value
- **Weeks 1–3:** pilot on one card segment, shadow mode (score, don't block)
- **Weeks 4–6:** go-live on highest-fraud MCC segments; measure FP rate + loss
- **Quarter 2:** expand divisions, add drift monitoring + scheduled retrain
Self-contained — no dependency on other platform migrations in flight.

---

### Slide 11 — The ask
Fund a 6-week pilot on one card segment. Success metric: **≥15% fraud-loss reduction with no
increase in false-positive declines**, measured on live traffic in shadow mode.

---

### Slide 12 — Appendix
Data model, feature list, model metrics (ROC-AUC, precision/recall), Genie question set,
latency benchmark. (See `docs/evidence/`.)
