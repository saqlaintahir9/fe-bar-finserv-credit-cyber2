# Genie Space Spec — Fraud & Credit Risk

A Genie Space so **SOC analysts (Cyber)** and **credit risk managers (Credit)** self-serve in
natural language instead of filing data-eng tickets.

## Tables exposed
- `shared_risk.fused_features` (gold)
- `shared_risk.flagged_cases` (score + GenAI narrative + analyst status)
- `credit.card_transactions`
- `cyber.auth_events`

(Exposed through UC — masking and row/column security still apply inside Genie.)

## Curated metrics / instructions
- **False-positive rate** = declined transactions later labeled legitimate ÷ all declines
- **Net fraud loss** = sum(amount) where fraud_label=1 AND decision=approve
- **ATO-linked** = case where `minutes_since_new_device_login < 15` AND `geo_mismatch_flag=1`
- Default time grain: hour. Default currency: USD. Treat "declines" as decision='decline'.

## Synonyms
ATO = account takeover; FP = false positive; MCC = merchant category; auth = authorization.

## Sample questions (capture answers → `docs/evidence/06_genie_qa.txt`)

**Demo account:**
0. Show ATO-linked cases for ACC-100042, including reason codes and narrative.

**Cyber / SOC:**
1. Show ATO-linked declines in the last hour by region.
2. Which device fingerprints appear across more than 5 accounts today?
3. What's the trend in new-device logins followed by a high-value purchase this week?

**Credit / Risk:**
4. What's today's false-positive decline rate on travel (MCC) transactions?
5. Top 10 highest-risk approved transactions right now, with the reason narrative.
6. How much net fraud loss did we avoid this week vs last week?
7. Average authorization decision latency by segment today.

**Shared / exec:**
8. Fraud loss avoided and false-positive rate, side by side, last 7 days.

Captured Q&A (SQL + rows) is in `docs/evidence/06_genie_qa.txt`.
