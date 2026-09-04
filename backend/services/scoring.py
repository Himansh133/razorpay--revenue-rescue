import pandas as pd
import numpy as np

WEIGHTS = {
    "payment_history": 0.25,
    "promise_history": 0.20,
    "ltv": 0.20,
    "recency": 0.20,
    "response_history": 0.15,
}

TIER_THRESHOLDS = {
    "high_priority": 0.70,
    "standard": 0.45,
    "low_priority": 0.25,
}

def classify_tier(score: float) -> str:
    if score >= TIER_THRESHOLDS["high_priority"]:
        return "high_priority"
    elif score >= TIER_THRESHOLDS["standard"]:
        return "standard"
    elif score >= TIER_THRESHOLDS["low_priority"]:
        return "low_priority"
    else:
        return "do_not_contact"

def rank_invoices(invoices_df: pd.DataFrame, customers_df: pd.DataFrame) -> pd.DataFrame:
    merged = invoices_df.merge(customers_df, on="customer_id", how="left")

    overdue_mask = merged["status"] == "overdue"
    df = merged[overdue_mask].copy()
    if df.empty:
        return pd.DataFrame()

    succ_pmts = df["successful_payments"] if "successful_payments" in df.columns else (df["successful_payments_count"] if "successful_payments_count" in df.columns else pd.Series(0, index=df.index))
    tot_orders = df["orders"] if "orders" in df.columns else (df["total_invoices_count"] if "total_invoices_count" in df.columns else pd.Series(1, index=df.index))
    df["payment_history_score"] = (succ_pmts.fillna(0) / (tot_orders.fillna(1) + 1e-6)).clip(0, 1)

    prom_kept = df["promises_kept"] if "promises_kept" in df.columns else (df["promises_kept_count"] if "promises_kept_count" in df.columns else pd.Series(0, index=df.index))
    prom_made = df["promises_made"] if "promises_made" in df.columns else (df["promises_made_count"] if "promises_made_count" in df.columns else pd.Series(1, index=df.index))
    df["promise_history_score"] = (prom_kept.fillna(0) / (prom_made.fillna(1) + 1e-6)).clip(0, 1)

    min_ltv, max_ltv = df["ltv"].min(), df["ltv"].max()
    df["ltv_score"] = (df["ltv"] - min_ltv) / (max_ltv - min_ltv + 1e-6)

    min_days, max_days = df["days_overdue"].min(), df["days_overdue"].max()
    df["recency_score"] = 1.0 - (df["days_overdue"] - min_days) / (max_days - min_days + 1e-6)

    em_opened = df["emails_opened_count"] if "emails_opened_count" in df.columns else (df["emails_opened"] if "emails_opened" in df.columns else pd.Series(0, index=df.index))
    em_sent = df["emails_sent_count"] if "emails_sent_count" in df.columns else (df["emails_sent"] if "emails_sent" in df.columns else pd.Series(1, index=df.index))
    df["response_history_score"] = (em_opened.fillna(0) / (em_sent.fillna(1) + 1e-6)).clip(0, 1)

    df["recovery_score"] = (
        WEIGHTS["payment_history"] * df["payment_history_score"] +
        WEIGHTS["promise_history"] * df["promise_history_score"] +
        WEIGHTS["ltv"] * df["ltv_score"] +
        WEIGHTS["recency"] * df["recency_score"] +
        WEIGHTS["response_history"] * df["response_history_score"]
    ).round(4)

    df["tier"] = df["recovery_score"].apply(classify_tier)
    df.sort_values(by="recovery_score", ascending=False, inplace=True)
    return df
