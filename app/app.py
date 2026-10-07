"""Fraud & Credit Risk Command Center — Databricks App (Streamlit)."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

DEMO = os.environ.get("DEMO_ACCOUNT", "ACC-100042")
CATALOG = os.environ.get("CATALOG", "fe_bar_meridian")
WAREHOUSE_ID = (
    os.environ.get("DATABRICKS_WAREHOUSE_ID")
    or os.environ.get("BPA_WAREHOUSE_ID")
    or "72255d4cf9534448"
).strip()
ROOT = Path(__file__).resolve().parent
GOLD = next(
    (
        p
        for p in (
            ROOT / "demo_gold.csv",
            ROOT.parent / "data" / "gold" / "fused_features.csv",
        )
        if p.exists()
    ),
    ROOT / "demo_gold.csv",
)
SQLITE = ROOT.parent / "data" / "lakebase_local.sqlite"
MODEL_CARD_PATH = ROOT / "ml_model_card.json"
NARRATIVE = (
    "A new device was registered on account ACC-100042 just 4 minutes before a "
    "transaction of $2318.47 was attempted, triggering multiple risk indicators "
    "including geographic inconsistencies and a burst of failed login attempts."
)
FEATURE_LABELS = {
    "recent_ato_label": "Account-takeover (ATO) signal",
    "device_is_new": "New device",
    "minutes_since_new_device_login": "Minutes since new-device login",
    "geo_mismatch_flag": "Geo mismatch (login vs home)",
    "failed_logins_1h": "Failed logins in last hour",
    "amount": "Transaction amount",
}
DEFAULT_CARD = {
    "model_version": "fused_gbm_v1",
    "uc_model": "fe_bar_meridian.shared_risk.fused_fraud_gbm",
    "roc_auc": 0.772,
    "demo_risk_score": 0.9,
    "feature_importances": {
        "amount": 0.8347,
        "minutes_since_new_device_login": 0.1542,
        "failed_logins_1h": 0.0093,
        "geo_mismatch_flag": 0.0017,
        "recent_ato_label": 0.0,
        "device_is_new": 0.0,
    },
    "demo_feature_values": {
        "amount": 2318.47,
        "minutes_since_new_device_login": 4.0,
        "geo_mismatch_flag": 1,
        "failed_logins_1h": 4,
        "recent_ato_label": 1,
        "device_is_new": 1,
    },
}


def load_model_card() -> dict:
    if MODEL_CARD_PATH.exists():
        try:
            return {**DEFAULT_CARD, **json.loads(MODEL_CARD_PATH.read_text())}
        except json.JSONDecodeError:
            return DEFAULT_CARD
    return DEFAULT_CARD


def top_contributors(case: dict, card: dict, n: int = 5) -> list[dict]:
    importances = card.get("feature_importances") or DEFAULT_CARD["feature_importances"]
    values = dict(card.get("demo_feature_values") or {})
    for key in importances:
        if case.get(key) is not None:
            values[key] = case[key]
    rows = []
    for name, importance in importances.items():
        raw = values.get(name)
        try:
            numeric = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            numeric = 0.0
        fired = numeric != 0
        importance_f = float(importance)
        # Fired ATO signals still appear even when Gini importance is near zero.
        contribution = importance_f if fired else 0.0
        if fired and contribution < 0.05:
            contribution = 0.05
        rows.append(
            {
                "feature": FEATURE_LABELS.get(name, name),
                "feature_key": name,
                "value": numeric,
                "importance": importance_f,
                "contribution": round(contribution, 4),
                "fired": "Yes" if fired else "No",
            }
        )
    rows.sort(key=lambda r: (r["contribution"], r["importance"]), reverse=True)
    return rows[:n]


def _workspace():
    from databricks.sdk import WorkspaceClient

    if os.environ.get("DATABRICKS_CLIENT_ID"):
        return WorkspaceClient()
    host = (os.environ.get("DATABRICKS_HOST") or "").rstrip("/")
    token = os.environ.get("DATABRICKS_TOKEN") or ""
    if host and token:
        return WorkspaceClient(host=host, token=token)
    return WorkspaceClient()


def _rows_to_df(resp) -> pd.DataFrame:
    manifest = getattr(resp, "manifest", None)
    result = getattr(resp, "result", None)
    cols = []
    if manifest and getattr(manifest, "schema", None):
        cols = [c.name for c in manifest.schema.columns]
    data = []
    if result and getattr(result, "data_array", None):
        data = result.data_array
    if not cols:
        return pd.DataFrame(data)
    return pd.DataFrame(data, columns=cols)


def _sql_cases() -> list[dict]:
    from databricks.sdk.service.sql import StatementState

    w = _workspace()
    try:
        w.warehouses.start(WAREHOUSE_ID)
    except Exception:
        pass
    sql = f"""
    SELECT f.txn_id, f.account_id, f.amount, f.reason_codes, f.txn_ts, f.decision,
           f.minutes_since_new_device_login, f.geo_mismatch_flag, f.failed_logins_1h,
           f.recent_ato_label, f.device_is_new,
           c.reason_narrative
    FROM {CATALOG}.shared_risk.fused_features f
    LEFT JOIN {CATALOG}.shared_risk.flagged_cases c ON f.txn_id = c.txn_id
    WHERE f.txn_id = 'TXN-DEMO-ATO' OR f.reason_codes LIKE '%ato_signal%'
    ORDER BY CASE WHEN f.txn_id = 'TXN-DEMO-ATO' THEN 0 ELSE 1 END
    LIMIT 12
    """
    resp = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=WAREHOUSE_ID,
        wait_timeout="0s",
    )
    sid = resp.statement_id
    deadline = time.time() + 90
    while time.time() < deadline:
        status = w.statement_execution.get_statement(sid)
        state = status.status.state
        if state == StatementState.SUCCEEDED:
            df = _rows_to_df(status)
            break
        if state in (StatementState.FAILED, StatementState.CANCELED, StatementState.CLOSED):
            err = getattr(status.status, "error", None)
            raise RuntimeError(err or state)
        time.sleep(1.5)
    else:
        raise TimeoutError("SQL warehouse query timed out")

    card = load_model_card()
    cases = []
    for _, r in df.iterrows():
        codes = [c for c in str(r.get("reason_codes") or "").split(",") if c]
        txn_id = r["txn_id"]
        score = float(r["risk_score"]) if "risk_score" in r and pd.notna(r.get("risk_score")) else (
            float(card["demo_risk_score"]) if txn_id == "TXN-DEMO-ATO" else None
        )
        cases.append(
            {
                "account_id": r["account_id"],
                "txn_id": txn_id,
                "amount": float(r["amount"] or 0),
                "risk_score": score,
                "model_version": card.get("model_version", "fused_gbm_v1"),
                "reason_codes": codes,
                "reason_narrative": r.get("reason_narrative")
                or (NARRATIVE if txn_id == "TXN-DEMO-ATO" else ""),
                "as_of": str(r.get("txn_ts")),
                "decision": r.get("decision"),
                "minutes_since_new_device_login": r.get("minutes_since_new_device_login"),
                "geo_mismatch_flag": r.get("geo_mismatch_flag"),
                "failed_logins_1h": r.get("failed_logins_1h"),
                "recent_ato_label": r.get("recent_ato_label"),
                "device_is_new": r.get("device_is_new"),
            }
        )
    if not cases:
        raise RuntimeError("Warehouse query returned no rows")
    return cases


def load_cases() -> list[dict]:
    try:
        return _sql_cases()
    except Exception as exc:
        st.warning(f"Warehouse read unavailable ({exc}); using local gold CSV if present.")
    if not GOLD.exists():
        return []
    card = load_model_card()
    df = pd.read_csv(GOLD)
    demo = df[df["txn_id"] == "TXN-DEMO-ATO"].copy()
    high = df[df["reason_codes"].fillna("").str.contains("ato_signal")].head(8)
    out = pd.concat([demo, high]).drop_duplicates("txn_id")
    cases = []
    for _, r in out.iterrows():
        codes = [c for c in str(r.get("reason_codes") or "").split(",") if c]
        cases.append(
            {
                "account_id": r["account_id"],
                "txn_id": r["txn_id"],
                "risk_score": float(r.get("risk_score") or 0),
                "model_version": str(r.get("model_version") or card.get("model_version") or "fused_gbm_v1"),
                "reason_codes": codes,
                "reason_narrative": NARRATIVE if r["txn_id"] == "TXN-DEMO-ATO" else "",
                "amount": float(r["amount"]),
                "decision": r.get("decision"),
                "as_of": str(r.get("txn_ts")),
                "minutes_since_new_device_login": r.get("minutes_since_new_device_login"),
                "geo_mismatch_flag": r.get("geo_mismatch_flag"),
                "failed_logins_1h": r.get("failed_logins_1h"),
                "recent_ato_label": r.get("recent_ato_label"),
                "device_is_new": r.get("device_is_new"),
            }
        )
    return cases


def sqlite_lookup() -> dict | None:
    if not SQLITE.exists():
        return None
    conn = sqlite3.connect(SQLITE)
    row = conn.execute(
        "SELECT account_id, txn_id, risk_score, reason_codes, amount, txn_ts, model_version FROM risk_scores WHERE account_id = ?",
        (DEMO,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "account_id": row[0],
        "txn_id": row[1],
        "score": row[2],
        "reason_codes": row[3].split(",") if row[3] else [],
        "amount": row[4],
        "as_of": str(row[5]),
        "model_version": row[6],
        "hot_path": f"GET /risk/{DEMO}",
    }


def render_ml_panel(case: dict, card: dict) -> None:
    score = case.get("risk_score")
    if score is None:
        score = card.get("demo_risk_score", 0.9)
    version = case.get("model_version") or card.get("model_version", "fused_gbm_v1")
    uc_model = card.get("uc_model", "fe_bar_meridian.shared_risk.fused_fraud_gbm")
    contributors = top_contributors(case, card)

    st.subheader("ML decision — fused fraud / credit-risk model")
    m1, m2, m3 = st.columns(3)
    m1.metric("Model risk score", f"{float(score):.2f}", help="GBM probability this authorization is fraud")
    m2.metric("Model version", version)
    m3.metric("UC registry", uc_model.split(".")[-1])
    st.caption(f"Registered model: `{uc_model}` · ROC-AUC {float(card.get('roc_auc', 0.772)):.3f} on synthetic holdout")

    st.markdown("**Top contributing features for this authorization**")
    contrib_df = pd.DataFrame(contributors)[["feature", "value", "importance", "fired"]]
    contrib_df = contrib_df.rename(
        columns={
            "feature": "Feature",
            "value": "This txn value",
            "importance": "Model importance",
            "fired": "Fired on this txn",
        }
    )
    st.dataframe(contrib_df, use_container_width=True, hide_index=True)
    chart_df = pd.DataFrame(contributors).set_index("feature")["importance"]
    st.bar_chart(chart_df)


card = load_model_card()
st.set_page_config(page_title="Fraud & Credit Risk Command Center", layout="wide")
st.title("Fraud & Credit Risk Command Center")
st.caption("Meridian Bank · fused Cyber ATO + Credit auth · synthetic data · ACC-100042")

col1, col2, col3 = st.columns(3)
col1.metric("Fraud loss avoided (illustrative)", "$7.0M")
col2.metric("FP decline target", "−30%")
col3.metric("Auth lookup SLA", "<50 ms p99 (in-region)")

division = st.radio("Division view", ["Shared", "Cyber", "Credit"], horizontal=True)
if division == "Cyber":
    st.info("Cyber view: ATO / device / geo signals. Fused score is shared; PAN stays masked.")
elif division == "Credit":
    st.info("Credit view: decisioning + fused score. Raw security columns stay masked.")

cases = load_cases()
st.subheader("Case queue")
queue = [
    {
        "account_id": c.get("account_id"),
        "txn_id": c.get("txn_id"),
        "risk_score": c.get("risk_score"),
        "model_version": c.get("model_version"),
        "amount": c.get("amount"),
        "decision": c.get("decision"),
        "reason_codes": ", ".join(c.get("reason_codes") or []),
    }
    for c in cases
]
st.dataframe(queue, use_container_width=True, hide_index=True)

demo_case = next((c for c in cases if c["txn_id"] == "TXN-DEMO-ATO"), cases[0] if cases else {})
render_ml_panel(demo_case, card)

st.subheader("Tell-show-tell: ACC-100042")
st.json(
    {
        "account_id": demo_case.get("account_id"),
        "txn_id": demo_case.get("txn_id"),
        "risk_score": demo_case.get("risk_score") or card.get("demo_risk_score"),
        "model_version": demo_case.get("model_version") or card.get("model_version"),
        "top_features": top_contributors(demo_case, card),
        "reason_codes": demo_case.get("reason_codes"),
        "reason_narrative": demo_case.get("reason_narrative"),
        "decision": demo_case.get("decision"),
        "as_of": demo_case.get("as_of"),
    }
)

hot = sqlite_lookup() or {}
hot.setdefault("account_id", DEMO)
hot.setdefault("score", demo_case.get("risk_score") or card.get("demo_risk_score"))
hot.setdefault("reason_codes", demo_case.get("reason_codes"))
hot.setdefault("narrative", demo_case.get("reason_narrative"))
hot.setdefault("model_version", demo_case.get("model_version") or card.get("model_version"))
hot.setdefault("as_of", demo_case.get("as_of"))
hot.setdefault("hot_path", f"GET /risk/{DEMO}")
hot["top_features"] = top_contributors(demo_case, card)
st.subheader("Hot-path contract GET /risk/ACC-100042")
st.code(json.dumps(hot, indent=2, default=str), language="json")

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "default_account": DEMO,
    "cases": cases[:5],
    "hot_path": hot,
}
st.caption("Genie: Show ATO-linked cases for ACC-100042")
if st.checkbox("Print case-queue JSON"):
    st.text(json.dumps(payload, indent=2, default=str))
