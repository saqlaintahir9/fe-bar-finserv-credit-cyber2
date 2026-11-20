# Talk track — Meridian Bank Fraud & Credit Risk demo (30 minutes)

**Audience**
- **Alex Morgan — business.** Accountable for fraud loss and the false-positive decline rate. Cares about dollars, customer impact, risk, and time to value.
- **Shreya — technical.** Owns the authorization platform, data, and model risk. Cares about latency, security, governance, and how it integrates.

**Goal of the call:** Alex and Shreya agree to a 6-week shadow-mode pilot on one card segment, with named owners and a date for the scoping session.

**Hard stop at 30:00.** Plan finishes at 28:00. Two minutes of buffer.

| Time | Segment | Lead persona | Slide / screen |
|---|---|---|---|
| 0:00–2:00 | Open, agenda, confirm priorities | Both | Slides 1–3 |
| 2:00–5:00 | Demo setup: the problem and what to watch for | Alex | Slides 4–5 |
| 5:00–7:00 | Value: the numbers we will move | Alex | Slide 6 |
| 7:00–19:00 | Live demo: four tell-show-tell chapters | Alternating | Slide 7, then Command Center + Genie |
| 19:00–20:30 | What you just saw | Both | Slide 11 |
| 20:30–26:00 | Questions | Both | Slides 8–10 as needed |
| 26:00–28:00 | Next steps and the ask | Alex, then Shreya | Slides 12–13 |
| 28:00–30:00 | Buffer, thank you | — | — |

---

## Before the call (10 minutes ahead)

1. Open the Command Center and wait for the queue to load. This warms the SQL warehouse (it auto-stops after 15 minutes).
   https://fe-bar-meridian-cmd-1444828305810485.aws.databricksapps.com
2. Open the Genie space in a second tab and run the ACC-100042 question once.
   https://e2-demo-field-eng.cloud.databricks.com/genie/rooms/01f1be1c7bba135f8491305e4038c5f4
3. Deck open in Presenter View on slide 1. Timer visible.
4. Backup if the app stalls: `docs/evidence/05_lakebase_lookup.txt` and `06_genie_qa.txt` have the same output as text.

---

## 0:00–2:00 · Open and agenda (both)

> "Alex, Shreya — thanks for the time. We have thirty minutes and I'll finish with a few to spare.
>
> Here's the plan. Three minutes on the problem as I understand it, then about twelve minutes live in the product, then your questions, and we'll close on whether a pilot makes sense.
>
> Before I start, two quick checks so I spend the time on what matters to you.
> Alex — is the bigger pressure right now fraud loss, or the good customers we're declining?
> Shreya — what would stop this from going near the authorization path on your side?"

**Listen. Reuse their words for the rest of the call.** If Alex says "declines," lead every value line with false declines. If Shreya says "latency," move Chapter 2 earlier.

*Delivery: slow down here. Make eye contact with each person as you name them.*

---

## 2:00–5:00 · Demo setup (Alex first)

**Slide 4 — the problem**

> "Meridian authorizes about forty million card transactions a month. You lose money at that moment in two ways.
>
> Fraud gets through: about thirty-five million dollars a year, roughly seven basis points of volume.
> And good customers get declined: about thirteen false declines for every real fraud. That's lost revenue, and those customers move their spend to another card.
>
> The root cause is simple. Cyber already sees the account takeover: the new device, the new location. Credit approves the purchase four minutes later without that signal. The two never meet in the authorization window."

**Slide 5 — what you are about to see**

> "In the demo I'll follow one account, ACC-100042. A new-device login from a new location, then a two-thousand-three-hundred-dollar online purchase four minutes later.
>
> Watch for four things:
> one, the case your fraud team sees;
> two, how fast the score is available at authorization;
> three, how Cyber and Credit data stay governed when they're combined;
> four, how your analysts get answers without filing a ticket.
>
> Alex, the first and last are for you. Shreya, the middle two are for you."

---

## 5:00–7:00 · Value (Alex)

**Slide 6 — outcomes**

> "Here's what this is worth, on illustrative numbers at Meridian's scale.
>
> Take twenty percent off thirty-five million in fraud loss: about seven million a year.
> Take thirty percent off the false declines: four to six million in recovered revenue.
> Together, eleven to thirteen million a year. The same fused signal moves both numbers.
>
> Shreya, the line that matters for you is the authorization lookup: under fifty milliseconds. I'll show you the measured number in a minute."

*Pause after "eleven to thirteen million." Let it land before moving on.*

---

## 7:00–19:00 · Live demo: four chapters, tell-show-tell

Show slide 7 for ten seconds ("four short chapters"), then switch to the Command Center.

Each chapter: **tell** what they will see (one sentence), **show** it, **tell** what it means for them (one sentence). About three minutes each.

### Chapter 1 · The case (Alex) — 7:00–10:00

**Tell:**
> "Alex, this is what your fraud team sees when an account is taken over and used within minutes."

**Show** — Command Center, sections 1 to 3:
- Section 1: the business numbers at the top. One sentence, don't reread them.
- Section 2: the case queue. "These are the accounts where Cyber and Credit signals fired together."
- Section 3: ACC-100042.
  - Timeline: new device at T0, the $2,318 purchase at T0 + 4 minutes.
  - **Model risk score 0.90**, model version `fused_gbm_v1`.
  - Top features: amount, minutes since the new-device login, failed logins, location mismatch.
  - Reason codes: `new_device_recent`, `geo_mismatch`, `failed_logins_burst`, `ato_signal`.
  - The analyst narrative in plain English.
  - **Recommended action: Hold and step-up authentication.**

**Tell:**
> "Without the Cyber signal, that purchase was approved. With it, the analyst holds it and verifies the cardholder. That's a fraud loss that never posts. The other side matters as much: when there's no takeover signal, the same score says approve, so you stop declining the good customer."

### Chapter 2 · Authorization-path speed (Shreya) — 10:00–13:00

**Tell:**
> "Shreya, your first question is usually: can this sit in the authorization path without breaking the SLA? Here's the measured answer."

**Show** — section 4, `GET /risk/ACC-100042`:
- The score comes from **Lakebase**, a managed Postgres database, with a single key lookup. No warehouse query and no join at authorization time.
- Point at the metric: **about 2 milliseconds at the median, under 4 milliseconds at the high end**, over 20 lookups from inside the region.
- The JSON payload is the contract your authorization service would call: score, reason codes, model version, timestamp.

**Tell:**
> "Two milliseconds against a fifty-millisecond budget. The heavy work, joining Cyber and Credit and scoring, happens ahead of time. At authorization it's one lookup. For Alex, that means we add the signal without slowing down a single approval."

*If Shreya pushes on the laptop number: "Over the public internet from my laptop it's about 80 milliseconds, which is network distance, not the database. The in-region number is the one your auth service would see."*

### Chapter 3 · Governance and model risk (Shreya, then Alex) — 13:00–16:00

**Tell:**
> "Combining Cyber and Credit data is where security and compliance usually stop the project. Here's how it stays governed."

**Show** — section 5, switch the division view between Shared, Cyber, and Credit:
- Same fused score in every view. Cyber sees device and location signals. Credit sees decisioning. Card numbers and emails stay masked by Unity Catalog in both.
- Back in section 3, point at the two different outputs:
  - **Reason codes** are the system of record for adverse-action notices and examiners.
  - **The narrative** is generated by AI from those codes, for the analyst only. It never writes the customer's decline letter.
- The model is versioned and registered in Unity Catalog: `fe_bar_meridian.shared_risk.fused_fraud_gbm`.

**Tell:**
> "Shreya, that's the model-risk and Reg B trail your examiners ask for, built in rather than bolted on. Alex, it means the audit evidence takes minutes, not a fire drill."

*Honest note if asked about row-level security: "Today the separation is column masking plus separate schemas. A row filter on the combined table is the next step. I didn't add it yet because it would have hidden this demo account from the app itself."*

### Chapter 4 · Ask the book in plain English (Alex) — 16:00–19:00

**Tell:**
> "Last piece, Alex: how your analysts get answers without waiting on data engineering."

**Show** — switch to the Genie tab:
- Type: **"Show ATO-linked cases for ACC-100042, including reason codes and narrative."**
- Point at the SQL Genie wrote, then the rows: same account, same codes, same narrative.
- Optional second question if time allows: "What's the false-positive decline rate this week?"

**Tell:**
> "That's a question that used to be a ticket and a two-day wait. Now the fraud lead asks it directly, on the same governed data. More of the team's time goes to working cases."

---

## 19:00–20:30 · What you just saw (both)

**Slide 11**

> "So, in twelve minutes:
> Alex, you saw a takeover-then-spend case caught in the authorization window, and the same signal that lets you approve good customers with confidence. That's the eleven-to-thirteen-million dual margin.
> Shreya, you saw a two-millisecond lookup against a fifty-millisecond budget, governed data across Cyber and Credit, and a model-risk trail examiners can follow.
>
> What questions do you have?"

*Stop talking. Let them go first.*

---

## 20:30–26:00 · Questions

Answer in about 30 seconds. **Alex: lead with dollars and risk. Shreya: give the mechanism, then close with what it means for the business.**

**Alex**

| Question | Answer |
|---|---|
| "What's the payback?" | "About seven million in avoided fraud and four to six million in recovered revenue a year. We prove it in a six-week shadow pilot before any live decision changes." |
| "What if the model is wrong?" | "That's why we start in shadow mode. The score runs alongside today's decision and blocks nothing. We only promote it if fraud loss goes down and false declines don't go up." |
| "How is this different from our fraud vendor?" | "A vendor scores the transaction on its own. The gap here is your own Cyber takeover signal reaching the authorization decision. You keep the data and the model." |
| "How long until we see value?" | "Six weeks on one card segment. It doesn't depend on any other migration finishing." |

**Shreya**

| Question | Answer |
|---|---|
| "How fresh are the features?" | "Login events stream in within seconds; transactions land in micro-batches. Scores are precomputed, so authorization never waits on a join. Freshness is bounded by the login stream, which is where the takeover signal comes from." |
| "How good is the model?" | "On synthetic holdout data, ROC-AUC is about 0.77, and precision and recall at a 0.5 threshold are modest. I'm not claiming it's production-ready. That's exactly why the pilot is shadow mode on your real traffic, with a threshold you tune." |
| "Security with Cyber and Credit combined?" | "Unity Catalog masks card numbers and email, the divisions sit in separate schemas, and only the fused score and reason codes are shared. Lineage runs from raw data to model to the lookup table." |
| "How does it plug into authorization?" | "Your authorization service adds one call: `GET /risk/{account_id}` against Lakebase. No change to the card rails." |
| "Model governance?" | "Tracked in MLflow and registered in Unity Catalog with versions, so every score ties back to a model version. That's the SR 11-7 trail." |

**If a question needs more than a minute:** "Good question. Let me take that into the scoping session so I give you a proper answer rather than a rushed one." Write it down where they can see you do it.

---

## 26:00–28:00 · Next steps and the ask

**Slide 12 — rollout, then slide 13 — next steps**

> "Here's what I'd propose.
>
> A six-week shadow-mode pilot on one card segment. Success is measured on your scorecard: at least fifteen percent less fraud loss, with no increase in false declines, on live traffic, before any decision changes.
>
> To get there, three concrete steps:
> One. Alex, pick the card segment and name a fraud-operations owner. Ideally the segment with the highest takeover losses.
> Two. Shreya, a ninety-minute technical scoping session next week: the authorization-service integration, the data feeds, and security review.
> Three. I'll send a one-page pilot plan with success metrics within two business days of this call, for both of you to sign off.
>
> Does next Tuesday or Wednesday work for the scoping session?"

**Get a date before you hang up.** If they hesitate: "What would you need to see to be comfortable starting?"

---

## 28:00–30:00 · Close

> "Thank you both. You'll have the pilot plan within two business days. Alex, Shreya — I appreciate the time."

---

## Delivery reminders

- **Pace:** about 140 words a minute. Pause after each number. Don't reread the slide.
- **Language:** "you" and "your team," not "the platform." Product names only when Shreya asks how.
- **Transitions:** name the next persona as you switch: "Shreya, this next part is for you."
- **Filler words:** replace "um" with a pause. Avoid "basically" and "just."
- **Time checks:** at 7:00 you should be in the demo. At 19:00 you should be recapping. If you're behind, cut the optional Genie question first, then shorten Chapter 3.
- **If the demo breaks:** "Let me show you the captured output instead," and open the evidence text file. Don't troubleshoot live.
