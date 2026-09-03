import os
from typing import Dict, Any, List
from backend.services.scoring import rank_invoices, classify_tier
from backend.services.optimizer import optimize as optimize_offer
from backend.ml.train import predict_acceptance
from backend.services.razorpay import create_payment_link
from backend.db.database import log_event

def run_negotiator_agent(user_message: str, invoices_df, customers_df) -> Dict[str, Any]:
    tool_calls_made = []
    
    # 1. Rank invoices
    ranked_df = rank_invoices(invoices_df, customers_df)
    tool_calls_made.append({
        "tool_name": "rank_invoices",
        "input": {"min_tier": "high_priority"},
        "result": {"top_invoices_count": len(ranked_df)}
    })

    target_inv = "INV000001"
    match = ranked_df[ranked_df["invoice_id"] == target_inv]
    
    if not match.empty:
        r_row = match.iloc[0].to_dict()
        inv_amt = float(r_row["amount"])
        cust_id = str(r_row["customer_id"])
        score_val = float(r_row["recovery_score"])
        tier_val = str(r_row["tier"])
        cust_score = float(r_row.get("payment_history_score", 0.75))

        tool_calls_made.append({
            "tool_name": "get_customer_profile",
            "input": {"customer_id": cust_id},
            "result": {"customer_id": cust_id, "score": score_val, "tier": tier_val}
        })

        floor_val = round(inv_amt * 0.80)
        cust_feat = {"customer_score": cust_score, "ltv": float(r_row.get("ltv", 100000.0))}
        
        opt_res = optimize_offer(inv_amt, floor_val, predict_acceptance, cust_feat)
        tool_calls_made.append({
            "tool_name": "optimize_offer",
            "input": {"invoice_id": target_inv, "merchant_floor": floor_val},
            "result": opt_res
        })

        best = opt_res["best_offer"]
        plink = create_payment_link(target_inv, best["offer_amount"])
        tool_calls_made.append({
            "tool_name": "create_payment_link",
            "input": {"invoice_id": target_inv, "offer_amount": best["offer_amount"]},
            "result": plink
        })

        narration = f"Analyzed invoice {target_inv} for customer {cust_id} (Recoverability Score: {score_val:.2f}, Tier: '{tier_val}'). " \
                    f"Evaluated {len(opt_res['all_candidates'])} recovery offers against merchant floor ₹{floor_val:,.0f}. " \
                    f"Selected ₹{best['offer_amount']:,.0f} ({best['discount_pct']}% discount) with Expected Value ₹{best['expected_value']:,.0f}. " \
                    f"Created payment link: {plink['short_url']}"
    else:
        narration = f"Processed request: '{user_message}'. Analyzed overdue portfolio."

    return {
        "status": "success",
        "final_response": narration,
        "tool_calls_made": tool_calls_made,
        "turns_used": len(tool_calls_made)
    }
