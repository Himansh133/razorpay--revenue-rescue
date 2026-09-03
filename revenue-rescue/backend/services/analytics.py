import os
import math
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from scipy.stats import norm

MIN_TRANSACTIONS = 50
Z_THRESHOLD = 2.58  # ~99% confidence
MIN_DROP = 0.05

def z_test_proportions(k_seg: int, n_seg: int, k_base: int, n_base: int):
    if n_seg < MIN_TRANSACTIONS or n_base < MIN_TRANSACTIONS:
        return 0.0, 1.0, 0.0

    p_seg = k_seg / n_seg
    p_base = k_base / n_base
    p_pool = (k_seg + k_base) / (n_seg + n_base)

    if p_pool == 0 or p_pool == 1:
        return 0.0, 1.0, p_base - p_seg

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_seg + 1 / n_base))
    if se == 0:
        return 0.0, 1.0, p_base - p_seg

    z = (p_base - p_seg) / se
    p_val = norm.sf(z)
    return z, p_val, p_base - p_seg

def estimate_rupee_impact(df_segment: pd.DataFrame, baseline_conversion: float) -> float:
    n_seg = len(df_segment)
    successful = df_segment["status"].eq("captured").sum()
    expected_successful = n_seg * baseline_conversion
    lost_conversions = max(0.0, expected_successful - successful)

    avg_ticket = df_segment.loc[df_segment["status"] == "captured", "amount"].mean()
    if pd.isna(avg_ticket) or avg_ticket == 0:
        avg_ticket = df_segment["amount"].mean()

    return float(lost_conversions * avg_ticket)

def scan_all_leaks(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []

    # Dynamic segment dimensions based on columns present in DataFrame
    possible_dims = [
        ["payment_method"],
        ["platform_os"],
        ["device"],
        ["city"],
        ["merchant_category"],
        ["payment_method", "platform_os"],
        ["payment_method", "device"],
        ["payment_method", "city"],
    ]

    valid_dimensions = [dim for dim in possible_dims if all(col in df.columns for col in dim)]

    k_global = df["status"].eq("captured").sum()
    n_global = len(df)
    global_conversion = k_global / n_global if n_global > 0 else 0.0

    flagged_leaks = []

    for dim in valid_dimensions:
        grouped = df.groupby(dim)
        for name, group in grouped:
            n_seg = len(group)
            if n_seg < MIN_TRANSACTIONS:
                continue

            k_seg = group["status"].eq("captured").sum()
            k_other = k_global - k_seg
            n_other = n_global - n_seg

            z, p_val, drop = z_test_proportions(k_seg, n_seg, k_other, n_other)

            if z >= Z_THRESHOLD and drop >= MIN_DROP:
                impact = estimate_rupee_impact(group, global_conversion)
                if isinstance(name, tuple):
                    segment_dict = dict(zip(dim, name))
                else:
                    segment_dict = {dim[0]: name}

                flagged_leaks.append({
                    "segment": segment_dict,
                    "dimension": " + ".join(dim),
                    "title": " + ".join([f"{v}" for v in segment_dict.values()]),
                    "n_transactions": int(n_seg),
                    "segment_conversion": float(k_seg / n_seg),
                    "baseline_conversion": float(global_conversion),
                    "z_score": float(z),
                    "p_value": float(p_val),
                    "drop_pct": float(drop),
                    "impact_rupees": round(impact, 2),
                    "confidence": float(round(1 - p_val, 4))
                })

    flagged_leaks.sort(key=lambda x: x["impact_rupees"], reverse=True)
    return flagged_leaks
