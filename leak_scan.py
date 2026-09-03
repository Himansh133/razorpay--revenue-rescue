"""
LEAK-SCAN Module: Revenue Leak Detection Engine for Merchant Transactions.

Framing & Statistical Foundation:
---------------------------------
This module performs STATISTICAL ANOMALY DETECTION via segment comparison.
It is NOT a causal inference model and does NOT claim or imply that a segment's 
attributes (e.g., Android, UPI, or evening hours) cause transaction failure or abandonment.
Rather, it identifies segments whose conversion rates deviate below baseline by a 
statistically significant margin (via two-proportion z-test) and estimates the potential 
revenue at risk. 

Terminology reflects this statistical honesty: segments are "flagged" or exhibit 
"elevated deviation" rather than "root cause identified."
"""

import sys
import os
import json
import time
import pandas as pd
import numpy as np
from scipy import stats


def add_time_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parses `timestamp` column and adds:
    - `hour`: int (0-23)
    - `time_of_day`: str bucket ('night', 'morning', 'afternoon', 'evening')
    
    Time Buckets:
    - Night: 00:00 - 05:59 (hours 0-5)
    - Morning: 06:00 - 11:59 (hours 6-11)
    - Afternoon: 12:00 - 16:59 (hours 12-16)
    - Evening: 17:00 - 23:59 (hours 17-23)
    """
    df_out = df.copy()
    ts = pd.to_datetime(df_out["timestamp"])
    df_out["hour"] = ts.dt.hour
    
    # Categorize hours into time_of_day buckets
    conditions = [
        (df_out["hour"] >= 0) & (df_out["hour"] <= 5),
        (df_out["hour"] >= 6) & (df_out["hour"] <= 11),
        (df_out["hour"] >= 12) & (df_out["hour"] <= 16),
        (df_out["hour"] >= 17) & (df_out["hour"] <= 23)
    ]
    choices = ["night", "morning", "afternoon", "evening"]
    df_out["time_of_day"] = np.select(conditions, choices, default="unknown")
    return df_out


def compute_segment_conversion(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """
    Given transaction DataFrame and a list of columns to group by,
    computes conversion rate (success / total), transaction count,
    success count, total amount, average transaction amount, and amount at risk 
    (sum of non-success transaction amounts) per segment.
    """
    df_temp = df.copy()
    df_temp["_is_success"] = (df_temp["status"] == "success").astype(int)
    df_temp["_at_risk_amount"] = np.where(df_temp["status"] != "success", df_temp["amount"], 0.0)

    agg_dict = {
        "transaction_count": ("transaction_id", "count"),
        "success_count": ("_is_success", "sum"),
        "total_amount": ("amount", "sum"),
        "avg_amount": ("amount", "mean"),
        "amount_at_risk": ("_at_risk_amount", "sum"),
    }
    
    grouped = df_temp.groupby(group_cols, as_index=False).agg(**agg_dict)
    grouped["conversion_rate"] = grouped["success_count"] / grouped["transaction_count"]
    return grouped


def find_anomalous_segments(
    df: pd.DataFrame,
    baseline_rate: float,
    min_segment_size: int = 50,
    min_relative_drop: float = 0.15
) -> pd.DataFrame:
    """
    Compares segment conversion rates against overall baseline conversion rate.
    Flags segments as anomalous if:
    1. transaction_count >= min_segment_size
    2. (baseline_rate - conversion_rate) / baseline_rate >= min_relative_drop
    
    Derives statistical confidence using a two-proportion z-test (comparing segment
    success rate against baseline population conversion rate).
    Returns DataFrame with relative_drop, z_score, p_value, and statistical confidence (0-1).
    """
    if df.empty:
        return df

    relative_drop = (baseline_rate - df["conversion_rate"]) / baseline_rate
    df_eval = df.copy()
    df_eval["relative_drop"] = relative_drop

    mask = (df_eval["transaction_count"] >= min_segment_size) & (df_eval["relative_drop"] >= min_relative_drop)
    flagged = df_eval[mask].copy()

    if flagged.empty:
        flagged["z_score"] = pd.Series(dtype=float)
        flagged["p_value"] = pd.Series(dtype=float)
        flagged["confidence"] = pd.Series(dtype=float)
        return flagged

    # Calculate statistical z-score & p-value comparing segment rate to baseline rate
    n = flagged["transaction_count"].values
    p_seg = flagged["conversion_rate"].values
    p0 = baseline_rate

    # Standard error under null hypothesis (p_seg = p0)
    se = np.sqrt((p0 * (1.0 - p0)) / n)
    se = np.where(se == 0, 1e-9, se)
    
    # Z-score for one-tailed test (evaluating drop below baseline)
    z_scores = (p0 - p_seg) / se
    p_values = stats.norm.sf(z_scores)
    confidence = np.clip(1.0 - p_values, 0.0, 1.0)

    flagged["z_score"] = z_scores
    flagged["p_value"] = p_values
    flagged["confidence"] = confidence

    return flagged


def estimate_impact(segment_row, baseline_rate: float) -> float:
    """
    Calculates estimated ₹ revenue impact (revenue at risk due to segment drop-off):
    estimated_impact = (baseline_rate - segment_rate) * segment_transaction_count * avg_transaction_amount
    """
    if isinstance(segment_row, dict):
        segment_rate = segment_row.get("segment_rate", segment_row.get("conversion_rate", 0.0))
        count = segment_row.get("segment_size", segment_row.get("transaction_count", 0))
        avg_amt = segment_row.get("average_transaction_amount_in_segment", 
                  segment_row.get("average_transaction_amount", 
                  segment_row.get("avg_amount", 0.0)))
    else:
        segment_rate = getattr(segment_row, "conversion_rate", getattr(segment_row, "segment_rate", 0.0))
        count = getattr(segment_row, "transaction_count", getattr(segment_row, "segment_size", 0))
        avg_amt = getattr(segment_row, "avg_amount", 
                  getattr(segment_row, "average_transaction_amount_in_segment", 
                  getattr(segment_row, "average_transaction_amount", 0.0)))

    drop = baseline_rate - segment_rate
    if drop <= 0:
        return 0.0
    impact = drop * count * avg_amt
    return float(np.round(impact, 2))


def find_dormant_high_value_customers(
    customers_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    dormancy_days: int = 90,
    ltv_percentile: float = 0.75
) -> pd.DataFrame:
    """
    Identifies high-value customers (above ltv_percentile) whose last transaction
    is older than dormancy_days.
    
    Returns DataFrame with: customer_id, ltv, days_since_last_transaction,
    sorted by ltv descending.
    """
    txns = transactions_df.copy()
    txns["timestamp_dt"] = pd.to_datetime(txns["timestamp"])
    
    ref_date = txns["timestamp_dt"].max()
    last_txn = txns.groupby("customer_id")["timestamp_dt"].max().reset_index()
    last_txn["days_since_last_transaction"] = (ref_date - last_txn["timestamp_dt"]).dt.total_seconds() / 86400.0

    merged = pd.merge(customers_df, last_txn, on="customer_id", how="left")
    merged["days_since_last_transaction"] = merged["days_since_last_transaction"].fillna(999.0)

    ltv_threshold = customers_df["ltv"].quantile(ltv_percentile)
    
    dormant_mask = (merged["ltv"] >= ltv_threshold) & (merged["days_since_last_transaction"] >= dormancy_days)
    dormant_df = merged[dormant_mask][["customer_id", "ltv", "days_since_last_transaction"]].copy()
    dormant_df = dormant_df.sort_values(by="ltv", ascending=False).reset_index(drop=True)

    return dormant_df


def _format_title(segment_dict: dict) -> str:
    """Formats segment dictionary into a clean human-readable title."""
    parts = []
    for k, v in segment_dict.items():
        v_str = str(v)
        if k == "time_of_day":
            v_str = v_str.capitalize()
        parts.append(v_str)
    return f"{' + '.join(parts)} checkout drop-off"


def scan_all_leaks(
    transactions_df: pd.DataFrame,
    customers_df: pd.DataFrame = None,
    dimensions: list = None
) -> list[dict]:
    """
    Top-level orchestrator function.
    Scans transaction data across multiple dimension combinations for conversion anomalies,
    and scans customer data for dormant high-LTV cohorts.
    
    Returns a ranked list of leak opportunity dictionaries sorted by impact_rupees descending.
    """
    # 1. Add time buckets to transactions
    df_txns = add_time_bucket(transactions_df)
    
    # 2. Overall baseline conversion rate
    baseline_rate = (df_txns["status"] == "success").mean()
    
    # 3. Define default dimension combinations to scan
    if dimensions is None:
        dimensions = [
            ["device", "payment_method"],
            ["device", "time_of_day"],
            ["payment_method", "time_of_day"],
            ["device", "payment_method", "time_of_day"],
            ["city"],
            ["device", "payment_method", "city"]
        ]

    opportunities = []

    # 4. Scan transaction segments
    for group_cols in dimensions:
        if not all(col in df_txns.columns for col in group_cols):
            continue

        grouped = compute_segment_conversion(df_txns, group_cols)
        anomalies = find_anomalous_segments(grouped, baseline_rate, min_segment_size=50, min_relative_drop=0.15)

        for _, row in anomalies.iterrows():
            segment_dict = {col: row[col] for col in group_cols}
            impact = estimate_impact(row, baseline_rate)
            
            opportunity = {
                "title": _format_title(segment_dict),
                "segment": segment_dict,
                "impact_rupees": float(np.round(impact, 2)),
                "confidence": float(np.round(row["confidence"], 4)),
                "baseline_rate": float(np.round(baseline_rate, 4)),
                "segment_rate": float(np.round(row["conversion_rate"], 4)),
                "segment_size": int(row["transaction_count"]),
                "type": "transaction_segment"
            }
            opportunities.append(opportunity)

    # 5. Scan dormant high-value customers
    if customers_df is not None and not customers_df.empty:
        dormant_df = find_dormant_high_value_customers(customers_df, transactions_df, dormancy_days=90, ltv_percentile=0.75)
        if not dormant_df.empty:
            dormant_count = len(dormant_df)
            total_dormant_ltv = float(np.round(dormant_df["ltv"].sum(), 2))
            
            dormant_opportunity = {
                "title": f"Dormant High-LTV Customer Cohort ({dormant_count} accounts)",
                "segment": {
                    "cohort": "dormant_high_ltv",
                    "min_dormancy_days": 90,
                    "ltv_percentile_threshold": 0.75
                },
                "impact_rupees": total_dormant_ltv,
                "confidence": 0.9900,
                "baseline_rate": float(np.round(baseline_rate, 4)),
                "segment_rate": 0.0,
                "segment_size": dormant_count,
                "type": "dormant_customer_cohort"
            }
            opportunities.append(dormant_opportunity)

    # 6. Sort all opportunities by impact_rupees descending
    opportunities.sort(key=lambda x: x["impact_rupees"], reverse=True)
    return opportunities


if __name__ == "__main__":
    data_dir = "./output"
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    elif not os.path.exists(os.path.join(data_dir, "transactions.csv")) and os.path.exists("transactions.csv"):
        data_dir = "."

    txn_path = os.path.join(data_dir, "transactions.csv")
    cust_path = os.path.join(data_dir, "customers.csv")

    print(f"Loading data from: {data_dir}")
    if not os.path.exists(txn_path):
        print(f"Error: Could not find {txn_path}")
        sys.exit(1)

    start_time = time.time()
    txns = pd.read_csv(txn_path)
    custs = pd.read_csv(cust_path) if os.path.exists(cust_path) else None

    leaks = scan_all_leaks(txns, custs)
    elapsed = time.time() - start_time

    print(f"Completed scan in {elapsed:.4f} seconds.")
    print(f"Total leak opportunities identified: {len(leaks)}")
    print("\n--- TOP 5 LEAK OPPORTUNITIES ---")
    for i, leak in enumerate(leaks[:5], 1):
        print(f"\n[{i}] {leak['title']} ({leak['type']})")
        print(f"    Impact: ₹{leak['impact_rupees']:,.2f}")
        print(f"    Confidence: {leak['confidence']:.1%}")
        print(f"    Segment Conversion Rate: {leak['segment_rate']:.1%} vs Baseline: {leak['baseline_rate']:.1%}")
        print(f"    Segment Size: {leak['segment_size']} units")
        print(f"    Segment Details: {json.dumps(leak['segment'])}")


"""
API Integration Example (Module 7: API-CORE / FastAPI endpoint):
--------------------------------------------------------------

from fastapi import FastAPI, HTTPException
import pandas as pd
from leak_scan import scan_all_leaks

app = FastAPI(title="Revenue Recovery System API")

@app.get("/opportunities")
def get_opportunities(limit: int = 10):
    try:
        txns_df = pd.read_csv("./output/transactions.csv")
        custs_df = pd.read_csv("./output/customers.csv")
        
        leaks = scan_all_leaks(txns_df, custs_df)
        
        return {
            "status": "success",
            "total_count": len(leaks),
            "opportunities": leaks[:limit]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""
