# Real-Time Fraud & Credit-Risk Intelligence (Financial Services)

End-to-end Databricks journey that fuses **Cyber** (account-takeover) and **Credit**
(card transaction / decisioning) signals into one governed, real-time risk platform for a
**synthetic large US card issuer (Meridian Bank)**.

Lakeflow → Unity Catalog → Lakebase → ML/GenAI → Genie → Databricks App.

Synthetic data only. PANs are tokens (`tok_…`). No real customer data.

**Demo account:** `ACC-100042` (ATO login → spend 4 minutes later). Same id in every stage.
Model score **0.90**, version **`fused_gbm_v1`**.

**Repo:** https://github.com/saqlaintahir9/fe-bar-finserv-credit-cyber2  
**Deck:** [`DECK.md`](DECK.md)

## Why this build

Cyber sees the ATO; Credit authorizes the spend; the signals never meet in the auth window.
This build joins them, scores via a Lakebase `GET /risk/{account_id}` lookup, attaches
structured reason codes plus an analyst narrative, and makes it queryable in Genie.
Buyer KPIs: fraud-loss bps and false-positive decline rate. See [`SOLUTION_SPEC.md`](SOLUTION_SPEC.md).

## Stages

| Stage | Component | File(s) | Evidence |
|---|---|---|---|
| Ingest | Lakeflow Spark Declarative Pipeline | `pipelines/fraud_credit_risk.py`, `pipelines/pipeline.yml` | `docs/evidence/01_lakeflow.txt` |
| Inspect | Pipeline notebook | `notebooks/01_lakeflow_pipeline.ipynb` | executed cells + 01 |
| Govern | UC masking, tags, grants | `notebooks/02_unity_catalog_governance.ipynb` | `docs/evidence/02_uc_grants.txt` |
| ML | GBM, MLflow, UC registry, `reason_codes` | `notebooks/03_train_score_model.ipynb` | `docs/evidence/03_model_metrics.txt` |
| GenAI | `AI_QUERY` narratives grounded in codes | `notebooks/04_genai_reason_narrative.ipynb` | `docs/evidence/04_genai_narratives.txt` |
| Serve | Lakebase key lookup | `notebooks/05_lakebase_serving.ipynb` | `docs/evidence/05_lakebase_lookup.txt` |
| Query | Genie Space | `docs/genie_space_spec.md` | `docs/evidence/06_genie_qa.txt` |
| Surface | Streamlit Command Center | `app/app.py`, `app/app.yaml` | `docs/evidence/07_app_case_queue.txt` |

## Layout

```
├── README.md
├── SOLUTION_SPEC.md
├── DECK.md
├── databricks.yml
├── src/generate_synthetic_data.py
├── src/run_gold_pipeline.py
├── pipelines/
├── notebooks/                 # executed, with cell output
├── app/
└── docs/evidence/
```

## Run locally (synthetic)

```bash
python src/generate_synthetic_data.py
python src/run_gold_pipeline.py
cd app && pip install -r requirements.txt && streamlit run app.py
```

## Live prototype (e2-demo-field-eng)

| Resource | Id / name |
|---|---|
| Catalog | `fe_bar_meridian` |
| SQL warehouse | `fe-bar-meridian` (`72255d4cf9534448`) |
| SQL gold | `fe_bar_meridian.shared_risk.fused_features` |
| Lakeflow SDP | `meridian-fraud-risk` (`e4f6bb45-3722-4b75-8933-c87ef838312f`) → `lakeflow_demo` |
| Lakebase | instance `fe-bar-meridian`; UC `fe_bar_meridian_lb.public.risk_scores` |
| UC model | `fe_bar_meridian.shared_risk.fused_fraud_gbm` versions **3–4 READY** |
| Genie Space | [Meridian Fraud and Credit Risk](https://e2-demo-field-eng.cloud.databricks.com/genie/rooms/01f1be1c7bba135f8491305e4038c5f4) |
| Databricks App | [fe-bar-meridian-cmd](https://fe-bar-meridian-cmd-1444828305810485.aws.databricksapps.com) |
| Demo thread | `ACC-100042` / `TXN-DEMO-ATO` / score **0.90** / `fused_gbm_v1` |
