# Demo and role-play notes

Two personas in the room at once. Walk the solution once, make the value case, then field
objections. Expect to **switch altitude mid-answer**.

## Opening frame (demo setup — say this first)
"Meridian Bank is a large card issuer: about 40 million authorizations a month. It loses money
twice at authorization — fraud slips through, and good customers get declined — because Cyber
sees the account-takeover and Credit never gets that signal in the auth window. I'll follow one
account, ACC-100042, through the fused score, and land what that means for fraud-loss bps and
false-positive declines."

## Demo spine
1. **Tell:** ACC-100042, new device + new geo, spend four minutes later.
2. **Show:** Command Center → **0.90** / `fused_gbm_v1` / top features → reason_codes → narrative grounded in those codes → Genie on that account.
3. **Tell:** loss avoided; same signal cuts over-declines.

---

## Business stakeholder (executive who funds it) — likely objections

| Objection | Answer (executive altitude) |
|---|---|
| "What's the ROI / payback?" | Dual-margin: ~$7M fraud avoided + $4–6M revenue recovered = ~$11–13M/yr. 6-week pilot, measured in shadow mode before we touch a single live decline. |
| "What's the risk if the model is wrong?" | Shadow mode first. ML is paired with deterministic **reason_codes** (velocity, geo-impossible, new device). GenAI never writes the legal decline letter — codes and features do. |
| "Time to value?" | Pilot on one segment in 6 weeks. It's self-contained — no dependency on other migrations. |
| "Why not buy a fraud vendor?" | Vendors score transactions in a silo; the differentiator is fusing *your* Cyber ATO signal into the auth path on data you already govern — and you keep the model and the data. |

## Technical stakeholder (architect / data lead) — likely objections

| Objection | Answer (technical altitude) |
|---|---|
| "Latency — a lakehouse query can't sit in the auth path." | Correct — that's why gold features + score sync to **Lakebase** (Postgres); the auth service does a single key lookup, <50 ms p99. The lakehouse does the heavy compute off the hot path. |
| "Data quality?" | Lakeflow expectations gate every bronze→silver→gold hop; bad rows quarantined, pass-rate is committed evidence. |
| "Security / PII — Cyber and Credit data together?" | Unity Catalog column masking on PAN/SSN and row-level separation by division. The *fused score* is shared, not the raw PII. Full lineage for audit. |
| "Model governance for exams?" | MLflow + UC registry (SR 11-7); versioned scores; **reason_codes** are the Reg B trail. GenAI is analyst presentation only. |
| "How does it integrate with card rails?" | Auth service adds `GET /risk/{account_id}` to Lakebase; no change to the rails. |
| "Freshness of fused features?" | Auth events are streaming / short-trigger; txns micro-batch. Hot path is a key lookup, not a join. |

## If the room shifts
- Business asks → lead with $ and risk, one sentence of how.
- Technical asks → give the real mechanism (Lakebase lookup, UC masking, MLflow) without
  losing the exec — close each technical answer with the business consequence.
