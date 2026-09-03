import json
import pandas as pd
from typing import Dict, Any, List
from backend.services.analytics import scan_all_leaks

def run_detective_scan(df_transactions: pd.DataFrame) -> Dict[str, Any]:
    leaks = scan_all_leaks(df_transactions)
    total_impact = sum(l["impact_rupees"] for l in leaks)

    findings = []
    for l in leaks[:3]:
        findings.append(
            f"Flagged segment '{l['title']}' with {l['drop_pct']*100:.1f}% conversion drop vs baseline. Estimated ₹ impact: ₹{l['impact_rupees']:,.0f}."
        )

    narration = f"Detective scanned {len(df_transactions):,} transactions and identified {len(leaks)} statistical revenue leaks totaling ₹{total_impact:,.0f} at risk."

    return {
        "status": "success",
        "leaks_found": len(leaks),
        "total_impact": total_impact,
        "findings": findings,
        "narration": narration
    }
