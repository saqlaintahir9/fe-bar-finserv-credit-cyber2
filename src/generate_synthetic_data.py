#!/usr/bin/env python3
"""Seeded synthetic Cyber + Credit data for the Meridian FE Bar build.

PAN values are tokens (tok_…) — never Luhn-valid card numbers.
Always injects demo account ACC-100042 with an ATO-then-spend sequence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 42
DEMO_ACCOUNT = "ACC-100042"
HOME_GEO = "US-NY"
GEOS = ["US-NY", "US-CA", "US-TX", "US-FL", "US-IL", "GB-LON", "DE-BER"]
MCCS = {
    "5411": "grocery",
    "5812": "restaurants",
    "5541": "gas",
    "7011": "hotels",
    "4511": "airlines",
    "5999": "misc_retail",
    "7995": "gambling",
    "5732": "electronics",
}


def tok_pan(account_id: str) -> str:
    digest = hashlib.sha256(f"pan|{account_id}|{SEED}".encode()).hexdigest()[:16]
    return f"tok_{digest}"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def build(n_accounts: int, n_txns: int, n_auths: int) -> dict:
    rng = random.Random(SEED)
    now = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)

    accounts = []
    account_ids = [DEMO_ACCOUNT] + [f"ACC-{200000 + i}" for i in range(1, n_accounts)]
    for i, aid in enumerate(account_ids):
        home = HOME_GEO if aid == DEMO_ACCOUNT else rng.choice(GEOS[:5])
        accounts.append(
            {
                "account_id": aid,
                "open_date": (now - timedelta(days=rng.randint(180, 2500))).date().isoformat(),
                "credit_limit": rng.choice([2500, 5000, 8000, 12000, 20000]),
                "segment": rng.choice(["mass", "mass_affluent", "premium"]),
                "home_geo": home,
                "email": f"user{aid.split('-')[1]}@example.invalid",
                "pan_token": tok_pan(aid),
            }
        )
    by_id = {a["account_id"]: a for a in accounts}

    # --- auth events ---
    auths = []
    # Demo: new device + new geo at T0
    t0 = now - timedelta(minutes=4)
    auths.append(
        {
            "event_id": "EVT-DEMO-ATO",
            "account_id": DEMO_ACCOUNT,
            "ts": t0.isoformat(),
            "device_id": "dev_new_91f2",
            "device_is_new": 1,
            "ip_geo": "GB-LON",
            "geo_is_new": 1,
            "auth_result": "success",
            "failed_attempts_1h": 4,
            "mfa_used": 0,
            "ato_label": 1,
        }
    )
    for i in range(n_auths - 1):
        acct = rng.choice(account_ids[1:])
        ts = now - timedelta(minutes=rng.randint(0, 14 * 24 * 60))
        home = by_id[acct]["home_geo"]
        is_new_dev = 1 if rng.random() < 0.08 else 0
        geo = rng.choice(GEOS) if is_new_dev and rng.random() < 0.5 else home
        fail = rng.randint(0, 6) if is_new_dev else rng.randint(0, 1)
        ato = 1 if (is_new_dev and geo != home and fail >= 3) else 0
        auths.append(
            {
                "event_id": f"EVT-{i:07d}",
                "account_id": acct,
                "ts": ts.isoformat(),
                "device_id": f"dev_{rng.randint(1, 9000):04d}" if is_new_dev else f"dev_known_{acct[-4:]}",
                "device_is_new": is_new_dev,
                "ip_geo": geo,
                "geo_is_new": int(geo != home),
                "auth_result": rng.choice(["success", "success", "success", "failure"]),
                "failed_attempts_1h": fail,
                "mfa_used": int(rng.random() < 0.7),
                "ato_label": ato,
            }
        )

    # --- transactions ---
    txns = []
    # Demo: high-value ecom 4 minutes after ATO
    t_spend = t0 + timedelta(minutes=4)
    txns.append(
        {
            "txn_id": "TXN-DEMO-ATO",
            "account_id": DEMO_ACCOUNT,
            "ts": t_spend.isoformat(),
            "amount": 2318.47,
            "mcc": "5732",
            "merchant_country": "GB",
            "channel": "ecom",
            "pan_token": tok_pan(DEMO_ACCOUNT),
            "decision": "approve",
            "fraud_label": 1,
        }
    )
    for i in range(n_txns - 1):
        acct = rng.choice(account_ids[1:])  # keep ACC-100042's only extra signal as the injected ATO spend
        ts = now - timedelta(minutes=rng.randint(0, 14 * 24 * 60))
        mcc = rng.choice(list(MCCS))
        amount = round(rng.lognormvariate(3.2, 0.9), 2)
        # inject some card-testing
        card_test = rng.random() < 0.03
        if card_test:
            amount = round(rng.uniform(1.0, 9.99), 2)
            mcc = "7995"
        fraud = 1 if card_test or (acct == DEMO_ACCOUNT and rng.random() < 0.02) else int(rng.random() < 0.012)
        # over-block some goods
        fp = (not fraud) and rng.random() < 0.015
        decision = "decline" if fraud and rng.random() < 0.35 or fp else "approve"
        if fraud and rng.random() < 0.45:
            decision = "approve"
        txns.append(
            {
                "txn_id": f"TXN-{i:07d}",
                "account_id": acct,
                "ts": ts.isoformat(),
                "amount": amount,
                "mcc": mcc,
                "merchant_country": rng.choice(["US", "US", "US", "GB", "CA"]),
                "channel": rng.choice(["ecom", "ecom", "card-present"]),
                "pan_token": tok_pan(acct),
                "decision": decision,
                "fraud_label": fraud,
            }
        )

    return {"accounts": accounts, "auth_events": auths, "card_transactions": txns}


def profile(payload: dict) -> str:
    tx = payload["card_transactions"]
    au = payload["auth_events"]
    ac = payload["accounts"]
    fraud = sum(int(r["fraud_label"]) for r in tx)
    declined = sum(1 for r in tx if r["decision"] == "decline")
    fp = sum(1 for r in tx if r["decision"] == "decline" and int(r["fraud_label"]) == 0)
    ato = sum(int(r["ato_label"]) for r in au)
    demo_tx = next(r for r in tx if r["account_id"] == DEMO_ACCOUNT and r["txn_id"] == "TXN-DEMO-ATO")
    demo_au = next(r for r in au if r["event_id"] == "EVT-DEMO-ATO")
    lines = [
        f"seed={SEED}",
        f"accounts={len(ac)} auth_events={len(au)} card_transactions={len(tx)}",
        f"fraud_label=1: {fraud} ({fraud / len(tx):.2%})",
        f"declines={declined} false_positive_declines={fp}",
        f"ato_label=1 auth events={ato}",
        f"demo_account={DEMO_ACCOUNT}",
        f"demo_auth={json.dumps(demo_au)}",
        f"demo_txn={json.dumps(demo_tx)}",
        f"sample_account={json.dumps(ac[0])}",
        f"sample_txn={json.dumps(tx[1])}",
        "pan_token_prefix=tok_ (no raw PAN generated)",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("data"))
    p.add_argument("--evidence", type=Path, default=Path("docs/evidence/00_data_profile.txt"))
    p.add_argument("--accounts", type=int, default=500)
    p.add_argument("--txns", type=int, default=8000)
    p.add_argument("--auths", type=int, default=3000)
    args = p.parse_args()

    payload = build(args.accounts, args.txns, args.auths)
    write_csv(
        args.out / "accounts.csv",
        payload["accounts"],
        ["account_id", "open_date", "credit_limit", "segment", "home_geo", "email", "pan_token"],
    )
    write_csv(
        args.out / "auth_events.csv",
        payload["auth_events"],
        [
            "event_id",
            "account_id",
            "ts",
            "device_id",
            "device_is_new",
            "ip_geo",
            "geo_is_new",
            "auth_result",
            "failed_attempts_1h",
            "mfa_used",
            "ato_label",
        ],
    )
    write_csv(
        args.out / "card_transactions.csv",
        payload["card_transactions"],
        [
            "txn_id",
            "account_id",
            "ts",
            "amount",
            "mcc",
            "merchant_country",
            "channel",
            "pan_token",
            "decision",
            "fraud_label",
        ],
    )
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    text = profile(payload)
    args.evidence.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
