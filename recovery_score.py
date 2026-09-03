"""
RECOVERY-SCORE Module: Heuristic Invoice Recovery Prioritization.

Framing & Methodology Constraint:
---------------------------------
This is a weighted heuristic, not a trained model. See ACCEPT-MODEL for the 
machine-learned acceptance-probability component.

RECOVERY-SCORE ranks whether an overdue invoice is worth entering into the recovery
pipeline before any offer or negotiation logic is run. It filters out low-probability,
high-annoyance-risk invoices so the system avoids unnecessary customer contact.
"""

import sys
import os
import time
import pandas as pd
import numpy as np


DEFAULT_WEIGHTS = {
    "payment_history_score": 0.30,
    "promise_history_score": 0.20,
    "ltv_score": 0.20,
    "recency_score": 0.15,
    "response_history_score": 0.15,
}


def normalize(series: pd.Series, invert: bool = False) -> pd.Series:
    """
    Min-max normalizes a pandas Series to [0, 1].
    If invert=True, higher raw values yield lower normalized scores.
    """
    min_val = series.min()
    max_val = series.max()
    
    if pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
        norm = pd.Series(0.5, index=series.index)
    else:
        norm = (series - min_val) / (max_val - min_val)
        
    if invert:
        norm = 1.0 - norm
        
    return norm


def compute_features(invoices_df: pd.DataFrame, customers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Joins invoices to customers on `customer_id` and derives five normalized 0-1 feature scores per invoice:
    - payment_history_score: successful_payments / orders (default 0.5 if orders == 0)
    - promise_history_score: promises_kept / promises_made (default 0.7 if promises_made == 0)
    - ltv_score: normalized LTV (higher LTV = higher score)
    - recency_score: inverse-normalized days_overdue (more overdue = lower score)
    - response_history_score: inverse-normalized avg_delay_days (lower delay = higher score)
    """
    df = pd.merge(invoices_df, customers_df, on="customer_id", how="left")

    # 1. Payment History Score (successful_payments / orders, default 0.5 if orders == 0)
    orders = df["orders"].fillna(0)
    succ_pmts = df["successful_payments"].fillna(0)
    raw_pmt_ratio = np.where(orders > 0, succ_pmts / orders, 0.5)
    df["payment_history_score"] = np.clip(raw_pmt_ratio, 0.0, 1.0)

    # 2. Promise History Score (promises_kept / promises_made, default 0.7 if promises_made == 0)
    promises_made = df["promises_made"].fillna(0)
    promises_kept = df["promises_kept"].fillna(0)
    raw_promise_ratio = np.where(promises_made > 0, promises_kept / promises_made, 0.7)
    df["promise_history_score"] = np.clip(raw_promise_ratio, 0.0, 1.0)

    # 3. LTV Score (higher LTV = higher score)
    df["ltv_score"] = normalize(df["ltv"].fillna(0), invert=False)

    # 4. Recency Score (inverse-normalized days_overdue; more overdue = lower score)
    df["recency_score"] = normalize(df["days_overdue"].fillna(0), invert=True)

    # 5. Response History Score (inverse-normalized avg_delay_days; higher delay = lower score)
    df["response_history_score"] = normalize(df["avg_delay_days"].fillna(0), invert=True)

    return df


def compute_recovery_score(features_df: pd.DataFrame, weights: dict = None) -> pd.Series:
    """
    Computes weighted sum of the five normalized feature scores.
    Validates that weights sum to 1.0.
    Returns pandas Series of recovery scores (0-1).
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    total_weight = sum(weights.values())
    if not np.isclose(total_weight, 1.0):
        raise ValueError(f"Weights must sum to 1.0, got {total_weight:.4f}")

    score = pd.Series(0.0, index=features_df.index)
    for feature_name, weight in weights.items():
        if feature_name not in features_df.columns:
            raise KeyError(f"Feature '{feature_name}' not found in features DataFrame.")
        score += features_df[feature_name] * weight

    return np.clip(score, 0.0, 1.0)


def classify_tier(score: float) -> str:
    """
    Classifies recovery score into operational priority tiers:
    - score >= 0.75 -> 'high_priority'
    - 0.50 <= score < 0.75 -> 'standard'
    - 0.30 <= score < 0.50 -> 'low_priority'
    - score < 0.30 -> 'do_not_chase' (Stopping rule: invoices excluded from recovery workflow)
    """
    if score >= 0.75:
        return "high_priority"
    elif score >= 0.50:
        return "standard"
    elif score >= 0.30:
        return "low_priority"
    else:
        return "do_not_chase"


def rank_invoices(
    invoices_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    weights: dict = None,
    min_amount: float = 0.0
) -> pd.DataFrame:
    """
    Top-level function. Computes features, computes recovery scores, joins back onto original 
    invoice data, filters to overdue invoices with amount >= min_amount, and sorts by score descending.
    
    Output columns:
    invoice_id, customer_id, amount, days_overdue, recovery_score, 
    payment_history_score, promise_history_score, ltv_score, recency_score, response_history_score
    """
    features_df = compute_features(invoices_df, customers_df)
    scores = compute_recovery_score(features_df, weights=weights)
    features_df["recovery_score"] = np.round(scores, 4)

    # Filter to status == 'overdue' and amount >= min_amount
    mask = (features_df["status"] == "overdue") & (features_df["amount"] >= min_amount)
    ranked = features_df[mask].copy()

    # Sort by recovery_score descending
    ranked = ranked.sort_values(by="recovery_score", ascending=False).reset_index(drop=True)

    # Select required columns
    output_cols = [
        "invoice_id",
        "customer_id",
        "amount",
        "days_overdue",
        "recovery_score",
        "payment_history_score",
        "promise_history_score",
        "ltv_score",
        "recency_score",
        "response_history_score",
    ]

    return ranked[output_cols]


if __name__ == "__main__":
    data_dir = "./output"
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    elif not os.path.exists(os.path.join(data_dir, "invoices.csv")) and os.path.exists("invoices.csv"):
        data_dir = "."

    inv_path = os.path.join(data_dir, "invoices.csv")
    cust_path = os.path.join(data_dir, "customers.csv")

    print(f"Loading data from: {data_dir}")
    if not os.path.exists(inv_path) or not os.path.exists(cust_path):
        print(f"Error: Could not find invoices.csv or customers.csv in {data_dir}")
        sys.exit(1)

    start_time = time.time()
    invoices = pd.read_csv(inv_path)
    customers = pd.read_csv(cust_path)

    ranked_df = rank_invoices(invoices, customers)
    elapsed = time.time() - start_time

    print(f"Completed invoice recovery ranking in {elapsed:.4f} seconds.")
    print(f"Total overdue invoices evaluated: {len(ranked_df)}")

    # Compute tier counts
    tiers = ranked_df["recovery_score"].apply(classify_tier)
    tier_counts = tiers.value_counts()

    print("\n--- RECOVERY TIER DISTRIBUTION ---")
    for tier_name in ["high_priority", "standard", "low_priority", "do_not_chase"]:
        count = tier_counts.get(tier_name, 0)
        pct = (count / len(ranked_df)) * 100 if len(ranked_df) > 0 else 0
        print(f"  {tier_name:<15}: {count:4d} invoices ({pct:.1f}%)")

    print("\n--- TOP 10 INVOICES (HIGHEST RECOVERY SCORE) ---")
    print(ranked_df.head(10).to_string(index=False))

    print("\n--- BOTTOM 10 INVOICES (LOWEST RECOVERY SCORE) ---")
    print(ranked_df.tail(10).to_string(index=False))


"""
API Integration Example (Module 7: API-CORE / FastAPI endpoint):
--------------------------------------------------------------

from fastapi import FastAPI, HTTPException
import pandas as pd
from recovery_score import rank_invoices, classify_tier

app = FastAPI(title="Revenue Recovery API")

@app.get("/invoices/recovery-pipeline")
def get_recovery_pipeline(min_amount: float = 0.0, exclude_do_not_chase: bool = True):
    try:
        invoices_df = pd.read_csv("./output/invoices.csv")
        customers_df = pd.read_csv("./output/customers.csv")
        
        ranked_df = rank_invoices(invoices_df, customers_df, min_amount=min_amount)
        
        # Apply stopping rules: filter out 'do_not_chase' tier if requested
        if exclude_do_not_chase:
            ranked_df["tier"] = ranked_df["recovery_score"].apply(classify_tier)
            ranked_df = ranked_df[ranked_df["tier"] != "do_not_chase"]
            
        return {
            "status": "success",
            "count": len(ranked_df),
            "invoices": ranked_df.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""
