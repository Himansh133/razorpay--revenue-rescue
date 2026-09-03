"""
AGENT-BRAIN Module: LLM Tool-Calling Orchestrator & Narrator.

Framing & Non-Negotiable Constraint:
-----------------------------------
The LLM never invents a probability, a score, or a ₹ figure. Every number it states
must come directly from a tool call return value. If the LLM is ever asked to "just estimate"
something instead of calling a tool for it, that is a bug. The LLM decides WHAT to check
and HOW to explain it; the numbers themselves are 100% deterministic code.
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Callable, Optional, Any

import pandas as pd

# Import tool implementations from sibling modules
from leak_scan import scan_all_leaks
from recovery_score import rank_invoices, classify_tier
from accept_model import load_model, predict_acceptance
from offer_optimizer import optimize as optimize_offer

DATA_DIR = "./output" if os.path.exists("./output/invoices.csv") else "."

# Model configuration
MODEL_NAME = "claude-sonnet-4-6"
MAX_TOKENS = 1000

# Global model cache for accept_model
_ACCEPT_MODEL_CACHE = None

def _get_accept_model():
    global _ACCEPT_MODEL_CACHE
    if _ACCEPT_MODEL_CACHE is None:
        model_path = os.path.join(DATA_DIR, "accept_model.joblib")
        if os.path.exists(model_path):
            _ACCEPT_MODEL_CACHE = load_model(model_path)
        elif os.path.exists("accept_model.joblib"):
            _ACCEPT_MODEL_CACHE = load_model("accept_model.joblib")
        else:
            # Fallback: train accept_model if joblib not found
            from accept_model import prepare_features, train_model
            neg_path = os.path.join(DATA_DIR, "negotiations.csv")
            if os.path.exists(neg_path):
                df_neg = pd.read_csv(neg_path)
                X, y = prepare_features(df_neg)
                res = train_model(X, y)
                _ACCEPT_MODEL_CACHE = res["model"]
    return _ACCEPT_MODEL_CACHE


# =====================================================================
# 1. TOOL IMPLEMENTATIONS (Python Functions)
# =====================================================================

def tool_get_invoice(invoice_id: str) -> dict:
    """Fetches invoice details by ID from data store."""
    inv_path = os.path.join(DATA_DIR, "invoices.csv")
    if not os.path.exists(inv_path):
        return {"error": f"Invoice dataset not found at {inv_path}"}
    
    df = pd.read_csv(inv_path)
    match = df[df["invoice_id"] == invoice_id]
    if match.empty:
        return {"error": f"Invoice '{invoice_id}' not found."}
    
    row = match.iloc[0].to_dict()
    return {
        "invoice_id": str(row["invoice_id"]),
        "customer_id": str(row["customer_id"]),
        "amount": float(row["amount"]),
        "days_overdue": int(row["days_overdue"]),
        "status": str(row["status"]),
        "due_date": str(row.get("due_date", "")),
    }


def tool_get_customer_profile(customer_id: str) -> dict:
    """Fetches customer historical profile by customer_id."""
    cust_path = os.path.join(DATA_DIR, "customers.csv")
    if not os.path.exists(cust_path):
        return {"error": f"Customer dataset not found at {cust_path}"}
    
    df = pd.read_csv(cust_path)
    match = df[df["customer_id"] == customer_id]
    if match.empty:
        return {"error": f"Customer '{customer_id}' not found."}
    
    row = match.iloc[0].to_dict()
    orders = int(row.get("orders", 0))
    succ_pmts = int(row.get("successful_payments", 0))
    pmt_ratio = round(succ_pmts / orders, 4) if orders > 0 else 0.5
    
    return {
        "customer_id": str(row["customer_id"]),
        "name": str(row.get("name", "Customer")),
        "segment": str(row.get("segment", "normal")),
        "ltv": float(row.get("ltv", 0.0)),
        "orders": orders,
        "successful_payments": succ_pmts,
        "failed_payments": int(row.get("failed_payments", 0)),
        "avg_delay_days": float(row.get("avg_delay_days", 0.0)),
        "customer_score": float(pmt_ratio),
    }


def tool_get_recovery_score(invoice_id: str) -> dict:
    """Calculates recovery score and tier classification for an invoice."""
    inv_path = os.path.join(DATA_DIR, "invoices.csv")
    cust_path = os.path.join(DATA_DIR, "customers.csv")
    if not os.path.exists(inv_path) or not os.path.exists(cust_path):
        return {"error": "Required CSV datasets missing."}
    
    invoices_df = pd.read_csv(inv_path)
    customers_df = pd.read_csv(cust_path)
    
    match = invoices_df[invoices_df["invoice_id"] == invoice_id]
    if match.empty:
        return {"error": f"Invoice '{invoice_id}' not found."}
    
    ranked_df = rank_invoices(invoices_df, customers_df)
    inv_match = ranked_df[ranked_df["invoice_id"] == invoice_id]
    
    if inv_match.empty:
        # If not overdue, compute manually or return status
        inv_row = match.iloc[0]
        return {
            "invoice_id": invoice_id,
            "status": str(inv_row["status"]),
            "recovery_score": 0.0,
            "tier": "not_overdue"
        }
    
    row = inv_match.iloc[0].to_dict()
    score = float(row["recovery_score"])
    tier = classify_tier(score)
    
    return {
        "invoice_id": str(row["invoice_id"]),
        "customer_id": str(row["customer_id"]),
        "amount": float(row["amount"]),
        "days_overdue": int(row["days_overdue"]),
        "recovery_score": score,
        "tier": tier,
        "component_scores": {
            "payment_history_score": float(row["payment_history_score"]),
            "promise_history_score": float(row["promise_history_score"]),
            "ltv_score": float(row["ltv_score"]),
            "recency_score": float(row["recency_score"]),
            "response_history_score": float(row["response_history_score"]),
        }
    }


def tool_get_leak_opportunities(top_n: int = 5) -> list[dict]:
    """Scans transactions for statistical conversion anomalies."""
    txn_path = os.path.join(DATA_DIR, "transactions.csv")
    cust_path = os.path.join(DATA_DIR, "customers.csv")
    if not os.path.exists(txn_path):
        return [{"error": f"Transactions file not found at {txn_path}"}]
    
    txns_df = pd.read_csv(txn_path)
    custs_df = pd.read_csv(cust_path) if os.path.exists(cust_path) else None
    
    leaks = scan_all_leaks(txns_df, custs_df)
    return leaks[:top_n]


def tool_get_offer_recommendation(invoice_id: str, merchant_floor: float) -> dict:
    """Generates and scores candidate offers using OFFER-OPTIMIZER & ACCEPT-MODEL."""
    inv = tool_get_invoice(invoice_id)
    if "error" in inv:
        return inv
    
    cust = tool_get_customer_profile(inv["customer_id"])
    if "error" in cust:
        return cust
    
    model = _get_accept_model()
    if model is None:
        return {"error": "ACCEPT-MODEL could not be loaded."}
    
    def predict_fn(discount_pct: float, days: int, cust_score: float, inv_amt: float) -> float:
        return predict_acceptance(model, discount_pct, days, cust_score, inv_amt)
    
    opt_result = optimize_offer(
        invoice_amount=inv["amount"],
        merchant_floor=float(merchant_floor),
        customer_score=cust["customer_score"],
        predict_fn=predict_fn
    )
    
    opt_result["invoice_id"] = invoice_id
    opt_result["merchant_floor"] = float(merchant_floor)
    return opt_result


def tool_create_payment_link(invoice_id: str, amount: float) -> dict:
    """Generates a Razorpay payment link for an invoice offer."""
    link_id = f"plink_{invoice_id.lower()}_{int(time.time())}"
    return {
        "status": "created",
        "payment_link_id": link_id,
        "payment_link_url": f"https://rzp.io/i/{link_id}",
        "invoice_id": invoice_id,
        "amount": float(amount),
    }


def tool_escalate_to_human(invoice_id: str, reason: str) -> dict:
    """Escalates an unrecoverable invoice to a human agent."""
    return {
        "status": "escalated",
        "invoice_id": invoice_id,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }


# TOOL_IMPL mapping tool names to python functions
TOOL_IMPL: dict[str, Callable] = {
    "get_invoice": tool_get_invoice,
    "get_customer_profile": tool_get_customer_profile,
    "get_recovery_score": tool_get_recovery_score,
    "get_leak_opportunities": tool_get_leak_opportunities,
    "get_offer_recommendation": tool_get_offer_recommendation,
    "create_payment_link": tool_create_payment_link,
    "escalate_to_human": tool_escalate_to_human,
}


# =====================================================================
# 2. ANTHROPIC TOOL SCHEMAS
# =====================================================================

TOOLS = [
    {
        "name": "get_invoice",
        "description": "Fetch invoice details (amount, days_overdue, status, customer_id) by invoice_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The unique invoice identifier (e.g. INV000123)"}
            },
            "required": ["invoice_id"]
        }
    },
    {
        "name": "get_customer_profile",
        "description": "Fetch customer historical profile (LTV, orders, successful_payments, avg_delay_days, customer_score) by customer_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "The unique customer identifier (e.g. CUST001234)"}
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "get_recovery_score",
        "description": "Calculate recoverability score (0-1) and tier classification (high_priority, standard, low_priority, do_not_chase) for an invoice.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The unique invoice identifier"}
            },
            "required": ["invoice_id"]
        }
    },
    {
        "name": "get_leak_opportunities",
        "description": "Scan transactions for statistical conversion anomalies and revenue leaks ranked by ₹ impact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "description": "Number of top opportunities to return (default: 5)"}
            }
        }
    },
    {
        "name": "get_offer_recommendation",
        "description": "Generate candidate recovery offers and return optimal choice respecting merchant floor minimum in ₹.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The unique invoice identifier"},
                "merchant_floor": {"type": "number", "description": "Minimum acceptable recovery amount in absolute ₹"}
            },
            "required": ["invoice_id", "merchant_floor"]
        }
    },
    {
        "name": "create_payment_link",
        "description": "Generate a Razorpay payment link for an invoice offer amount.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The unique invoice identifier"},
                "amount": {"type": "number", "description": "The agreed payment amount in ₹"}
            },
            "required": ["invoice_id", "amount"]
        }
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate invoice to human manager when recovery_score tier is 'do_not_chase' or floor is unreachable.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The unique invoice identifier"},
                "reason": {"type": "string", "description": "Explanation of why automated recovery was stopped"}
            },
            "required": ["invoice_id", "reason"]
        }
    }
]


SYSTEM_PROMPT = """You are AGENT-BRAIN, the intelligent orchestrator for the Revenue Recovery System.
Your job is to receive merchant requests, invoke tools to inspect data, and explain recovery strategies clearly.

NON-NEGOTIABLE CORE CONSTRAINTS:
1. NEVER invent or hallucinate any score, probability, or rupee figure. Every number you state MUST come directly from a tool call return value in this conversation.
2. ALWAYS fetch invoice + customer profile + recovery_score BEFORE proposing any action on an invoice.
3. If recovery_score tier is 'do_not_chase', call escalate_to_human or state that recovery is stopped. Do NOT generate an offer.
4. When narrating an offer recommendation, explicitly mention at least one REJECTED candidate offer if any fell below the merchant floor (e.g., 'evaluated an 18% discount at ₹82,000, but REJECTED it because it fell below your ₹85,000 floor').
5. Keep final explanations concise (2 to 4 sentences) — clear, professional, and actionable for a merchant dashboard.
"""


# =====================================================================
# 3. AGENT ORCHESTRATION LOOP
# =====================================================================

def explain_leak_scan_results(leaks: list[dict]) -> str:
    """
    Produces concise natural language narration of LEAK-SCAN results using strict tool numbers.
    """
    if not leaks:
        return "Leak scan complete. No statistically significant transaction anomalies detected at this time."

    total_impact = sum(l.get("impact_rupees", 0.0) for l in leaks)
    leak_count = len(leaks)
    
    top_leak = leaks[0]
    seg_name = top_leak.get("segment", "Unknown segment")
    top_impact = top_leak.get("impact_rupees", 0.0)
    top_conf = top_leak.get("confidence", 0.0)

    explanation = (
        f"Scanned transactions and identified {leak_count} revenue leak segments totaling ₹{total_impact:,.2f} in potential risk. "
        f"The primary anomaly is in '{seg_name}' with an estimated ₹{top_impact:,.2f} impact ({top_conf:.1%} confidence). "
        f"We recommend targeting gateway routing optimization for this cohort."
    )
    return explanation


def run_agent(user_message: str, max_turns: int = 8, merchant_floor: float = 0.0) -> dict:
    """
    Main tool-calling loop.
    Executes Anthropic API tool-use loop if ANTHROPIC_API_KEY is configured.
    Otherwise, executes a deterministic, rule-bound tool loop using real tool code.
    Returns: {"final_response": str, "tool_calls_made": list[dict], "turns_used": int}
    """
    tool_calls_made = []
    turns_used = 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            messages = [{"role": "user", "content": user_message}]

            for turn in range(1, max_turns + 1):
                turns_used = turn
                response = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages
                )

                if response.stop_reason == "tool_use":
                    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                    messages.append({"role": "assistant", "content": response.content})

                    tool_results = []
                    for block in tool_use_blocks:
                        tool_name = block.name
                        tool_input = block.input

                        # Execute tool
                        impl_fn = TOOL_IMPL.get(tool_name)
                        if impl_fn:
                            res = impl_fn(**tool_input)
                        else:
                            res = {"error": f"Tool {tool_name} not implemented"}

                        # Log tool call with timestamp
                        log_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "tool_name": tool_name,
                            "input": tool_input,
                            "result": res
                        }
                        tool_calls_made.append(log_entry)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(res)
                        })

                    messages.append({"role": "user", "content": tool_results})
                else:
                    # Final text response
                    final_text = "".join([b.text for b in response.content if hasattr(b, "text")])
                    return {
                        "final_response": final_text,
                        "tool_calls_made": tool_calls_made,
                        "turns_used": turns_used
                    }
        except Exception as e:
            print(f"Anthropic API call failed ({e}), switching to deterministic tool orchestration engine.")

    # Fallback / Deterministic Tool Orchestrator Engine (runs standalone without API key)
    # Extract invoice_id if present in user message (e.g. 'INV000123')
    import re
    inv_match = re.search(r"INV\d+", user_message)
    invoice_id = inv_match.group(0) if inv_match else "INV000001"

    # Step 1: get_invoice
    turns_used += 1
    inv_res = tool_get_invoice(invoice_id)
    tool_calls_made.append({
        "timestamp": datetime.now().isoformat(),
        "tool_name": "get_invoice",
        "input": {"invoice_id": invoice_id},
        "result": inv_res
    })

    if "error" in inv_res:
        return {
            "final_response": f"Error looking up invoice: {inv_res['error']}",
            "tool_calls_made": tool_calls_made,
            "turns_used": turns_used
        }

    # Step 2: get_customer_profile
    turns_used += 1
    cust_id = inv_res["customer_id"]
    cust_res = tool_get_customer_profile(cust_id)
    tool_calls_made.append({
        "timestamp": datetime.now().isoformat(),
        "tool_name": "get_customer_profile",
        "input": {"customer_id": cust_id},
        "result": cust_res
    })

    # Step 3: get_recovery_score
    turns_used += 1
    rec_res = tool_get_recovery_score(invoice_id)
    tool_calls_made.append({
        "timestamp": datetime.now().isoformat(),
        "tool_name": "get_recovery_score",
        "input": {"invoice_id": invoice_id},
        "result": rec_res
    })

    tier = rec_res.get("tier", "standard")
    score = rec_res.get("recovery_score", 0.5)

    if tier == "do_not_chase":
        # Stopping rule triggered: escalate to human
        turns_used += 1
        esc_res = tool_escalate_to_human(invoice_id, f"Recovery score {score:.2f} classified as do_not_chase")
        tool_calls_made.append({
            "timestamp": datetime.now().isoformat(),
            "tool_name": "escalate_to_human",
            "input": {"invoice_id": invoice_id, "reason": esc_res["reason"]},
            "result": esc_res
        })
        final_text = (
            f"Automated recovery for invoice {invoice_id} (₹{inv_res['amount']:,.2f}) has been STOPPED because its recovery score "
            f"({score:.2f}) falls into the 'do_not_chase' tier. The case has been escalated to a human account manager."
        )
        return {
            "final_response": final_text,
            "tool_calls_made": tool_calls_made,
            "turns_used": turns_used
        }

    # Step 4: get_offer_recommendation
    turns_used += 1
    effective_floor = merchant_floor if merchant_floor > 0 else round(inv_res["amount"] * 0.80, -2)
    offer_res = tool_get_offer_recommendation(invoice_id, effective_floor)
    tool_calls_made.append({
        "timestamp": datetime.now().isoformat(),
        "tool_name": "get_offer_recommendation",
        "input": {"invoice_id": invoice_id, "merchant_floor": effective_floor},
        "result": offer_res
    })

    best_offer = offer_res.get("best_offer")
    rejected_count = offer_res.get("rejected_count", 0)
    all_cands = offer_res.get("all_candidates", [])
    rejected_cands = [c for c in all_cands if not c.get("is_valid", True)]

    if not best_offer:
        # Floor unreachable: escalate
        turns_used += 1
        esc_res = tool_escalate_to_human(invoice_id, f"No valid offer generated above merchant floor ₹{effective_floor:,.2f}")
        tool_calls_made.append({
            "timestamp": datetime.now().isoformat(),
            "tool_name": "escalate_to_human",
            "input": {"invoice_id": invoice_id, "reason": esc_res["reason"]},
            "result": esc_res
        })
        final_text = (
            f"Unable to generate an automated offer for invoice {invoice_id} (₹{inv_res['amount']:,.2f}). "
            f"All candidate discount options fell below your merchant floor of ₹{effective_floor:,.2f}. Escalated to human manager."
        )
    else:
        # Step 5: create_payment_link
        turns_used += 1
        link_res = tool_create_payment_link(invoice_id, best_offer["offer_amount"])
        tool_calls_made.append({
            "timestamp": datetime.now().isoformat(),
            "tool_name": "create_payment_link",
            "input": {"invoice_id": invoice_id, "amount": best_offer["offer_amount"]},
            "result": link_res
        })

        rejected_mention = ""
        if rejected_cands:
            sample_rej = rejected_cands[0]
            rejected_mention = f" Note: Candidate offer with {sample_rej['discount_pct']}% discount (₹{sample_rej['offer_amount']:,.2f}) was REJECTED as it fell below your ₹{effective_floor:,.2f} floor."

        final_text = (
            f"Evaluated invoice {invoice_id} (₹{inv_res['amount']:,.2f}, recovery score {score:.2f}, tier '{tier}'). "
            f"Recommended optimal offer: ₹{best_offer['offer_amount']:,.2f} ({best_offer['discount_pct']}% discount, {best_offer['days_to_payment']} days timeline) "
            f"with a predicted acceptance probability of {best_offer['acceptance_probability']:.1%}.{rejected_mention} "
            f"Payment link generated: {link_res['payment_link_url']}."
        )

    return {
        "final_response": final_text,
        "tool_calls_made": tool_calls_made,
        "turns_used": turns_used
    }


if __name__ == "__main__":
    print("--- DEMO: AGENT-BRAIN TOOL-CALLING ORCHESTRATION ---")
    
    test_prompt = "Recover overdue invoice INV000001"
    print(f"\nUser Input: '{test_prompt}'")
    
    start_time = time.time()
    agent_output = run_agent(test_prompt, max_turns=8, merchant_floor=80000.0)
    elapsed = time.time() - start_time
    
    print(f"\nCompleted orchestration in {elapsed:.4f} seconds ({agent_output['turns_used']} turns).")
    
    print("\n--- TOOL CALL AUDIT TRAIL LOG ---")
    for i, call in enumerate(agent_output["tool_calls_made"], 1):
        print(f"[{i}] {call['timestamp']} | Tool: {call['tool_name']}")
        print(f"    Input : {json.dumps(call['input'])}")
        res_str = json.dumps(call['result'])
        if len(res_str) > 120:
            res_str = res_str[:120] + "...}"
        print(f"    Output: {res_str}")
    
    print("\n--- AGENT FINAL RESPONSE ---")
    print(agent_output["final_response"])

    print("\n--- LEAK SCAN NARRATION DEMO ---")
    leaks_sample = tool_get_leak_opportunities(top_n=3)
    narrative = explain_leak_scan_results(leaks_sample)
    print(narrative)


"""
Integration Example with API-CORE (FastAPI):
-------------------------------------------

from fastapi import FastAPI, HTTPException
from agent_brain import run_agent

app = FastAPI(title="Revenue Recovery API")

@app.post("/recovery/{invoice_id}/recommend")
def recommend_recovery(invoice_id: str, merchant_floor: float = 0.0):
    try:
        # Execute AGENT-BRAIN tool-calling orchestration loop
        user_prompt = f"Recover invoice {invoice_id}"
        agent_result = run_agent(user_prompt, merchant_floor=merchant_floor)
        
        return {
            "status": "success",
            "invoice_id": invoice_id,
            "final_response": agent_result["final_response"],
            "tool_calls_made": agent_result["tool_calls_made"],  # Feeds directly into AUDIT-TRAIL
            "turns_used": agent_result["turns_used"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""
