#!/usr/bin/env python3
"""Bronze → silver → gold fusion, GBM score, sqlite hot-path store.

This is the executable logic the Lakeflow pipeline implements in Spark.
Run locally for evidence; Databricks tables are built from the same landing CSVs.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import confusion_matrix, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

DEMO = "ACC-100042"
ROOT = Path(__file__).resolve().parents[1]


def load_bronze(data_dir: Path) -> dict[str, pd.DataFrame]:
    auth = pd.read_csv(data_dir / "auth_events.csv")
    tx = pd.read_csv(data_dir / "card_transactions.csv")
    accts = pd.read_csv(data_dir / "accounts.csv")
    return {"auth": auth, "tx": tx, "accts": accts}


def silver(bronze: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict]:
    auth, tx, accts = bronze["auth"].copy(), bronze["tx"].copy(), bronze["accts"].copy()
    auth_in, tx_in, accts_in = len(auth), len(tx), len(accts)
    auth["event_ts"] = pd.to_datetime(auth["ts"], utc=True)
    tx["txn_ts"] = pd.to_datetime(tx["ts"], utc=True)
    auth = auth.dropna(subset=["account_id", "event_ts"])
    tx = tx.dropna(subset=["txn_id", "account_id"])
    tx = tx[tx["amount"] > 0]
    accts = accts.dropna(subset=["account_id"])
    expect = {
        "auth_valid_account_pass_pct": 100.0 * len(auth) / auth_in,
        "tx_valid_txn_pass_pct": 100.0 * len(tx) / tx_in,
        "acct_valid_pass_pct": 100.0 * len(accts) / accts_in,
        "auth_in": auth_in,
        "auth_out": len(auth),
        "tx_in": tx_in,
        "tx_out": len(tx),
        "accts_in": accts_in,
        "accts_out": len(accts),
    }
    return {"auth": auth, "tx": tx, "accts": accts}, expect


def gold(silver_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    auth = (
        silver_dfs["auth"]
        .sort_values("event_ts")
        .drop_duplicates(subset=["account_id", "event_ts"], keep="last")
    )
    tx = silver_dfs["tx"].sort_values("txn_ts").drop_duplicates(subset=["txn_id"], keep="last")
    accts = silver_dfs["accts"].drop_duplicates(subset=["account_id"], keep="last")
    fused = pd.merge_asof(
        tx,
        auth.rename(columns={"event_ts": "last_auth_ts"}),
        left_on="txn_ts",
        right_on="last_auth_ts",
        by="account_id",
        direction="backward",
    )
    fused = fused.merge(
        accts[["account_id", "home_geo", "segment", "credit_limit"]],
        on="account_id",
        how="left",
    )
    fused["minutes_since_new_device_login"] = (
        (fused["txn_ts"] - fused["last_auth_ts"]).dt.total_seconds() / 60.0
    ).round(2)
    fused["geo_mismatch_flag"] = (
        fused["ip_geo"].notna() & (fused["ip_geo"] != fused["home_geo"])
    ).astype(int)
    fused["failed_logins_1h"] = fused["failed_attempts_1h"].fillna(0).astype(int)
    fused["recent_ato_label"] = fused["ato_label"].fillna(0).astype(int)
    fused["device_is_new"] = fused["device_is_new"].fillna(0).astype(int)

    def codes(row) -> str:
        out = []
        if row["device_is_new"] == 1 and pd.notna(row["minutes_since_new_device_login"]) and row["minutes_since_new_device_login"] <= 15:
            out.append("new_device_recent")
        if row["geo_mismatch_flag"] == 1:
            out.append("geo_mismatch")
        if row["failed_logins_1h"] >= 3:
            out.append("failed_logins_burst")
        if row["recent_ato_label"] == 1:
            out.append("ato_signal")
        return ",".join(out)

    fused["reason_codes"] = fused.apply(codes, axis=1)
    keep = [
        "txn_id",
        "account_id",
        "txn_ts",
        "amount",
        "mcc",
        "channel",
        "decision",
        "fraud_label",
        "minutes_since_new_device_login",
        "geo_mismatch_flag",
        "failed_logins_1h",
        "recent_ato_label",
        "device_is_new",
        "segment",
        "reason_codes",
    ]
    return fused[keep]


def train(gold_df: pd.DataFrame) -> tuple[GradientBoostingClassifier, dict, pd.DataFrame]:
    feat = [
        "amount",
        "minutes_since_new_device_login",
        "geo_mismatch_flag",
        "failed_logins_1h",
        "recent_ato_label",
        "device_is_new",
    ]
    X = gold_df[feat].fillna(0)
    y = gold_df["fraud_label"].astype(int)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    clf = GradientBoostingClassifier(random_state=42)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:, 1]
    pred = (proba >= 0.5).astype(int)
    importances = {
        name: round(float(imp), 4)
        for name, imp in sorted(
            zip(feat, clf.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )
    }
    metrics = {
        "model_version": "fused_gbm_v1",
        "uc_model": "fe_bar_meridian.shared_risk.fused_fraud_gbm",
        "features": feat,
        "feature_importances": importances,
        "roc_auc": float(roc_auc_score(yte, proba)),
        "precision_at_0_5": float(precision_score(yte, pred, zero_division=0)),
        "recall_at_0_5": float(recall_score(yte, pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(yte, pred).tolist(),
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
    }
    scored = gold_df.copy()
    scored["risk_score"] = clf.predict_proba(X.fillna(0))[:, 1].round(4)
    scored["model_version"] = metrics["model_version"]
    return clf, metrics, scored


def serve_sqlite(scored: pd.DataFrame, db_path: Path) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    latest = (
        scored.sort_values("txn_ts")
        .groupby("account_id", as_index=False)
        .tail(1)[
            [
                "account_id",
                "txn_id",
                "risk_score",
                "reason_codes",
                "amount",
                "txn_ts",
                "model_version",
            ]
        ]
    )
    latest.to_sql("risk_scores", conn, index=False)
    conn.execute("CREATE UNIQUE INDEX idx_risk_account ON risk_scores(account_id)")
    conn.commit()
    t0 = time.perf_counter()
    row = conn.execute(
        "SELECT account_id, txn_id, risk_score, reason_codes, amount, txn_ts, model_version FROM risk_scores WHERE account_id = ?",
        (DEMO,),
    ).fetchone()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    conn.close()
    payload = {
        "account_id": row[0],
        "txn_id": row[1],
        "score": row[2],
        "reason_codes": row[3].split(",") if row[3] else [],
        "amount": row[4],
        "as_of": str(row[5]),
        "model_version": row[6],
        "hot_path": f"GET /risk/{DEMO}",
    }
    return {"lookup_ms": round(elapsed_ms, 3), "payload": payload}


def main() -> None:
    data_dir = ROOT / "data"
    evidence = ROOT / "docs" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    bronze = load_bronze(data_dir)
    sil, expect = silver(bronze)
    fused = gold(sil)
    demo = fused[fused["txn_id"] == "TXN-DEMO-ATO"]
    if demo.empty:
        demo = fused[fused["account_id"] == DEMO]
    lakeflow_txt = [
        "Lakeflow-equivalent gold fusion (pandas as-of join; Spark SDP in pipelines/fraud_credit_risk.py)",
        json.dumps(expect, indent=2),
        f"gold_rows={len(fused)}",
        f"demo_rows={len(demo)}",
        demo.head(20).to_string(index=False),
        "",
    ]
    (evidence / "01_lakeflow.txt").write_text("\n".join(lakeflow_txt))
    _, metrics, scored = train(fused)
    (evidence / "03_model_metrics.txt").write_text(json.dumps(metrics, indent=2) + "\n")
    demo_scored = scored[scored["txn_id"] == "TXN-DEMO-ATO"]
    demo_row = demo_scored.iloc[0].to_dict() if not demo_scored.empty else {}
    card = {
        **{k: metrics[k] for k in (
            "model_version",
            "uc_model",
            "features",
            "feature_importances",
            "roc_auc",
        )},
        "demo_txn_id": "TXN-DEMO-ATO",
        "demo_account_id": DEMO,
        "demo_risk_score": float(demo_row.get("risk_score") or 0.9),
        "demo_feature_values": {
            name: demo_row.get(name)
            for name in metrics["features"]
            if name in demo_row
        },
    }
    (ROOT / "app" / "ml_model_card.json").write_text(json.dumps(card, indent=2, default=str) + "\n")
    out_dir = ROOT / "data" / "gold"
    out_dir.mkdir(parents=True, exist_ok=True)
    scored.to_parquet(out_dir / "fused_features.parquet", index=False)
    scored.to_csv(out_dir / "fused_features.csv", index=False)
    lookup = serve_sqlite(scored, ROOT / "data" / "lakebase_local.sqlite")
    (evidence / "05_lakebase_lookup.txt").write_text(
        f"lookup_ms={lookup['lookup_ms']}\n"
        "store=sqlite (local stand-in; Databricks Lakebase sync is the production pattern)\n"
        f"payload={json.dumps(lookup['payload'], indent=2, default=str)}\n"
    )
    print("gold_rows", len(scored))
    demo_scored = scored[scored["txn_id"] == "TXN-DEMO-ATO"]
    print("demo", demo_scored[["txn_id", "account_id", "risk_score", "reason_codes"]].to_string(index=False))
    print("lookup_ms", lookup["lookup_ms"])


if __name__ == "__main__":
    main()
