# Meridian Bank — Real-Time Fraud & Credit-Risk Intelligence

**Audience:** Alex Morgan (business — fraud loss and false declines) and Shreya (technical — authorization platform, data, model risk)
**Customer (synthetic):** Meridian Bank — large US card issuer (~$50B volume, ~40M authorizations a month)
**Format:** 30-minute demo, about 12 minutes live in the product. Slides with speaker notes: [`DECK.pptx`](DECK.pptx). Word-for-word timing: [`docs/talk_track.md`](docs/talk_track.md).

---

### 1 — Title
**Stop paying twice: cut fraud loss and stop declining good customers.** Prepared for Alex Morgan and Shreya.

### 2 — Our 30 minutes
0–5 problem and what you'll see · 5–7 value · 7–19 live demo · 19–26 questions · 26–28 next steps.

### 3 — What I want to make sure we cover
- **Alex:** fraud loss, good customers declined, risk if the model is wrong, how fast we can prove it.
- **Shreya:** latency in the authorization window, security when Cyber and Credit meet, model-risk trail, what changes for the authorization service.

Confirm both on the call before starting.

### 4 — The problem
Meridian loses money at authorization twice: **~$35M a year** in fraud (about 7 bps) and **13 false declines for every real fraud**. Cyber sees the takeover; Credit approves the purchase four minutes later without that signal.

### 5 — What you're about to see (demo setup)
One account, **ACC-100042**: new-device login, then a $2,318 online purchase four minutes later. Watch for:
1. The case your fraud team sees *(Alex)*
2. Speed at authorization *(Shreya)*
3. Governed Cyber + Credit data *(Shreya)*
4. Answers without a ticket *(Alex)*

### 6 — What it's worth

| Outcome | Today | Target | Annual value | Who feels it |
|---|---|---|---|---|
| Fraud loss | ~$35M / yr | −20% | ~$7.0M avoided | Alex |
| False declines | 13 : 1 | −30% | ~$4–6M recovered | Alex |
| Authorization lookup | 120–300 ms | <50 ms | No SLA impact | Shreya |
| Takeover time-to-detect | minutes–hours | <1 s | Less dwell time | Both |
| Audit evidence | days | minutes | Exam-ready | Shreya |

**Combined: ~$11–13M a year.** Illustrative on synthetic data at Meridian's scale.

### 7 — The demo: four tell-show-tell chapters
| Chapter | Show | So what |
|---|---|---|
| 1 The case | Queue → ACC-100042 → score 0.90 → reason codes → hold and step-up | Fraud loss that never posts |
| 2 Speed | `GET /risk/ACC-100042` from Lakebase, timed live | Signal added, no slower approvals |
| 3 Governance | Division views, masked card data, reason codes vs. AI narrative | Examiner trail in minutes |
| 4 Ask the book | Genie question → SQL → governed rows | Analysts work cases, not tickets |

### 8 — How it works
Lakeflow → Unity Catalog → ML + GenAI → Lakebase → Command Center + Genie. Heavy work happens ahead of time; at authorization it's one key lookup. **Measured in-region: p50 2.1 ms, p99 under 4 ms.**

### 9 — Shreya: running it in production
Latency, freshness, security, model risk, integration, and model quality. Each answer gives the mechanism, then what it means for Meridian. Model quality is stated plainly: holdout ROC-AUC ~0.77, modest precision and recall, so the pilot starts in shadow mode.

### 10 — Compliance and model risk
Reg B reasons come from reason codes and features; AI never writes the customer notice. SR 11-7 via MLflow + UC registry. FCRA lineage, PCI/GLBA tokenization and masking, BSA/AML auditability.

### 11 — What you just saw
- **Alex:** a takeover caught in the authorization window, with a clear action, and good customers approved with confidence. ~$11–13M a year.
- **Shreya:** a 2 ms lookup against a 50 ms budget, governed Cyber + Credit data, an examiner-ready model trail.

### 12 — Rollout
Weeks 1–3 shadow mode on one segment · Weeks 4–6 promote if fraud loss is down ≥15% and false declines aren't up · Quarter 2 scale, drift monitoring, retraining.

### 13 — Next steps
1. **Alex** — choose the pilot card segment and name a fraud-operations owner. *This week.*
2. **Shreya** — 90-minute technical scoping: integration, data feeds, security review. *Next Tuesday or Wednesday.*
3. **Me** — one-page pilot plan with success metrics for sign-off. *Within 2 business days.*

### 14 — Appendix
Data, model, serving, and live-environment details. See `docs/evidence/`.
