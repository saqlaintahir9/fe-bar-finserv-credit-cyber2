# Lakeflow Spark Declarative Pipeline — fused Cyber + Credit gold features.
# Deploy with: databricks bundle deploy && databricks bundle run meridian_fraud_risk
# Notebook 01 inspects this pipeline; it does not replace it.

import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window

CATALOG = spark.conf.get("bpa.catalog", "fe_bar_meridian")
LANDING = spark.conf.get(
    "bpa.landing",
    f"/Volumes/{CATALOG}/shared_risk/landing",
)


@dlt.table(comment="Raw Cyber auth/login events (streaming / short-trigger)")
def bronze_auth_events():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .load(f"{LANDING}/auth_events/")
    )


@dlt.table(comment="Raw Credit card authorizations (micro-batch landing)")
def bronze_card_transactions():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .load(f"{LANDING}/card_transactions/")
    )


@dlt.table(comment="Account master")
def bronze_accounts():
    return spark.read.format("csv").option("header", "true").load(f"{LANDING}/accounts/")


@dlt.table(comment="Typed Cyber auth events")
@dlt.expect_or_drop("valid_account", "account_id IS NOT NULL")
@dlt.expect("ts_present", "event_ts IS NOT NULL")
def silver_auth_events():
    return dlt.read_stream("bronze_auth_events").select(
        F.col("event_id").cast("string"),
        F.col("account_id").cast("string"),
        F.to_timestamp("ts").alias("event_ts"),
        F.col("device_id").cast("string"),
        F.col("device_is_new").cast("int"),
        F.col("ip_geo").cast("string"),
        F.col("geo_is_new").cast("int"),
        F.col("auth_result").cast("string"),
        F.col("failed_attempts_1h").cast("int"),
        F.col("mfa_used").cast("int"),
        F.col("ato_label").cast("int"),
    )


@dlt.table(comment="Typed Credit transactions")
@dlt.expect_or_drop("valid_txn", "txn_id IS NOT NULL AND account_id IS NOT NULL")
@dlt.expect_or_drop("valid_amount", "amount > 0")
def silver_card_transactions():
    return dlt.read_stream("bronze_card_transactions").select(
        F.col("txn_id").cast("string"),
        F.col("account_id").cast("string"),
        F.to_timestamp("ts").alias("txn_ts"),
        F.col("amount").cast("double"),
        F.col("mcc").cast("string"),
        F.col("merchant_country").cast("string"),
        F.col("channel").cast("string"),
        F.col("pan_token").cast("string"),
        F.col("decision").cast("string"),
        F.col("fraud_label").cast("int"),
    )


@dlt.table(comment="Typed accounts")
@dlt.expect_or_drop("valid_acct_master", "account_id IS NOT NULL")
def silver_accounts():
    return dlt.read("bronze_accounts").select(
        F.col("account_id").cast("string"),
        F.to_date("open_date").alias("open_date"),
        F.col("credit_limit").cast("double"),
        F.col("segment").cast("string"),
        F.col("home_geo").cast("string"),
        F.col("email").cast("string"),
        F.col("pan_token").cast("string"),
    )


@dlt.table(
    name="fused_features",
    comment="Gold fused Cyber+Credit features. Latest auth event per account as-of txn_ts is approximated via last auth row.",
)
def fused_features():
    tx = dlt.read_stream("silver_card_transactions")
    # Snapshot of auth (stream-static join). Production: as-of / ASOF join with watermark.
    w = Window.partitionBy("account_id").orderBy(F.col("event_ts").desc())
    latest_auth = (
        dlt.read("silver_auth_events")
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .select(
            "account_id",
            F.col("event_ts").alias("last_auth_ts"),
            "device_is_new",
            "geo_is_new",
            "failed_attempts_1h",
            "ato_label",
            "ip_geo",
        )
    )
    accts = dlt.read("silver_accounts").select(
        "account_id", "home_geo", "segment", "credit_limit"
    )

    return (
        tx.join(latest_auth, "account_id", "left")
        .join(accts, "account_id", "left")
        .withColumn(
            "minutes_since_new_device_login",
            F.round((F.unix_timestamp("txn_ts") - F.unix_timestamp("last_auth_ts")) / 60.0, 2),
        )
        .withColumn(
            "geo_mismatch_flag",
            F.when(
                F.col("ip_geo").isNotNull() & (F.col("ip_geo") != F.col("home_geo")),
                F.lit(1),
            ).otherwise(F.lit(0)),
        )
        .withColumn(
            "reason_codes",
            F.concat_ws(
                ",",
                F.when(
                    (F.col("device_is_new") == 1)
                    & (F.col("minutes_since_new_device_login") <= 15),
                    F.lit("new_device_recent"),
                ),
                F.when(F.col("geo_mismatch_flag") == 1, F.lit("geo_mismatch")),
                F.when(F.col("failed_attempts_1h") >= 3, F.lit("failed_logins_burst")),
                F.when(F.col("ato_label") == 1, F.lit("ato_signal")),
            ),
        )
        .select(
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
            F.col("failed_attempts_1h").alias("failed_logins_1h"),
            F.col("ato_label").alias("recent_ato_label"),
            "segment",
            "reason_codes",
        )
    )
