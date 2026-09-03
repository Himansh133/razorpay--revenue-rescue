"""
API-CORE: FastAPI Backend & Integration Routing Layer

Endpoints Overview:
1. GET  /health                        - Health check & API status.
2. GET  /opportunities                 - Discovered revenue leaks ranked by ₹ impact (LEAK-SCAN).
3. GET  /invoices                      - Overdue invoices ranked by recoverability score & tier (RECOVERY-SCORE).
4. GET  /invoices/{invoice_id}         - Detailed invoice breakdown + joined customer profile & component scores.
5. POST /recovery/{invoice_id}/recommend - Deterministic candidate offer optimization & floor enforcement (OFFER-OPTIMIZER).
6. POST /recovery/{invoice_id}/execute - Generates Razorpay payment link & registers pending payment (PAY-BRIDGE).
7. POST /webhooks/razorpay             - Razorpay webhook handler for payment.captured events & recovery tracking.
8. POST /agent/ask                     - LLM tool-calling orchestration & natural language narration (AGENT-BRAIN).
9. GET  /dashboard/summary             - Top-level financial aggregation (risk, recoverable, recovered).
"""

import os
import json
import time
from contextlib import asynccontextmanager
from typing import Optional, Any

import pandas as pd
from fastapi import FastAPI, Request, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

# Import modules
from leak_scan import scan_all_leaks
from recovery_score import rank_invoices, classify_tier
from accept_model import load_model, predict_acceptance
from offer_optimizer import optimize as optimize_offer
from agent_brain import run_agent, explain_leak_scan_results
from pay_bridge import create_payment_link, verify_webhook_signature, parse_webhook_event
from audit_trail import log_event, log_from_agent_run, get_trail, get_trail_summary
from models import (
    HealthResponse,
    OpportunityItem,
    OpportunitiesResponse,
    InvoiceSummaryItem,
    InvoicesResponse,
    InvoiceDetailResponse,
    CustomerProfile,
    RecoveryScoreBreakdown,
    RecommendRequest,
    RecommendResponse,
    ExecuteRequest,
    ExecuteResponse,
    WebhookResponse,
    AgentAskRequest,
    AgentAskResponse,
    DashboardSummaryResponse,
)

DATA_DIR = "./output" if os.path.exists("./output/invoices.csv") else "."

# In-memory storage for state tracking across API calls
state_store = {
    "invoices_df": None,
    "customers_df": None,
    "transactions_df": None,
    "negotiations_df": None,
    "accept_model": None,
    "recovered_store": {},     # {invoice_id: float_amount}
    "executions_store": {},    # {invoice_id: {offer_amount, payment_link_id, payment_link_url}}
}


def load_dataset_state():
    """Loads CSV files and trained models into memory."""
    inv_path = os.path.join(DATA_DIR, "invoices.csv")
    cust_path = os.path.join(DATA_DIR, "customers.csv")
    txn_path = os.path.join(DATA_DIR, "transactions.csv")
    neg_path = os.path.join(DATA_DIR, "negotiations.csv")

    if os.path.exists(inv_path):
        state_store["invoices_df"] = pd.read_csv(inv_path)
    if os.path.exists(cust_path):
        state_store["customers_df"] = pd.read_csv(cust_path)
    if os.path.exists(txn_path):
        state_store["transactions_df"] = pd.read_csv(txn_path)
    if os.path.exists(neg_path):
        state_store["negotiations_df"] = pd.read_csv(neg_path)

    # Load machine-learned accept model
    model_path = os.path.join(DATA_DIR, "accept_model.joblib")
    if os.path.exists(model_path):
        state_store["accept_model"] = load_model(model_path)
    elif os.path.exists("accept_model.joblib"):
        state_store["accept_model"] = load_model("accept_model.joblib")
    else:
        # Fallback: train accept_model if missing
        if state_store["negotiations_df"] is not None:
            from accept_model import prepare_features, train_model
            X, y = prepare_features(state_store["negotiations_df"])
            res = train_model(X, y)
            state_store["accept_model"] = res["model"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler: loads data at startup."""
    load_dataset_state()
    yield


app = FastAPI(
    title="AI Revenue Recovery System API",
    description="Production integration backend for revenue leak scanning, invoice recovery scoring, offer optimization, and AGENT-BRAIN orchestration.",
    version="1.0.0",
    lifespan=lifespan
)

# Permissive CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# 1. GET /health
# =====================================================================
@app.get("/health", response_model=HealthResponse, tags=["System"])
def get_health():
    """Returns API health status."""
    return HealthResponse(status="ok", data_dir=DATA_DIR)


# =====================================================================
# 2. GET /opportunities
# =====================================================================
@app.get("/opportunities", response_model=OpportunitiesResponse, tags=["LEAK-SCAN"])
def get_opportunities(top_n: int = Query(default=5, ge=1, le=50)):
    """Calls LEAK-SCAN to discover and rank conversion anomalies by ₹ impact."""
    try:
        if state_store["transactions_df"] is None:
            load_dataset_state()

        if state_store["transactions_df"] is None:
            raise HTTPException(status_code=404, detail="Transactions dataset not found.")

        leaks = scan_all_leaks(state_store["transactions_df"], state_store["customers_df"])
        return OpportunitiesResponse(
            status="success",
            total_leaks=len(leaks),
            opportunities=leaks[:top_n]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LEAK-SCAN error: {str(e)}")


# =====================================================================
# 3. GET /invoices
# =====================================================================
@app.get("/invoices", response_model=InvoicesResponse, tags=["RECOVERY-SCORE"])
def get_invoices(
    tier: Optional[str] = Query(default=None, description="Filter by priority tier: high_priority, standard, low_priority, do_not_chase"),
    min_amount: float = Query(default=0.0, ge=0.0, description="Filter by minimum invoice amount in ₹")
):
    """Calls RECOVERY-SCORE to rank overdue invoices by recoverability."""
    try:
        if state_store["invoices_df"] is None or state_store["customers_df"] is None:
            load_dataset_state()

        if state_store["invoices_df"] is None or state_store["customers_df"] is None:
            raise HTTPException(status_code=404, detail="Invoice or customer dataset not found.")

        ranked_df = rank_invoices(
            state_store["invoices_df"],
            state_store["customers_df"],
            min_amount=min_amount
        )
        ranked_df["tier"] = ranked_df["recovery_score"].apply(classify_tier)

        if tier:
            ranked_df = ranked_df[ranked_df["tier"] == tier.lower()]

        records = ranked_df.to_dict(orient="records")
        invoice_items = [InvoiceSummaryItem(**rec) for rec in records]

        return InvoicesResponse(
            status="success",
            total_count=len(invoice_items),
            invoices=invoice_items
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RECOVERY-SCORE error: {str(e)}")


# =====================================================================
# 4. GET /invoices/{invoice_id}
# =====================================================================
@app.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse, tags=["Invoices"])
def get_invoice_detail(invoice_id: str):
    """Returns single invoice details, joined customer profile, and recovery score breakdown."""
    try:
        if state_store["invoices_df"] is None or state_store["customers_df"] is None:
            load_dataset_state()

        inv_df = state_store["invoices_df"]
        cust_df = state_store["customers_df"]

        match_inv = inv_df[inv_df["invoice_id"] == invoice_id]
        if match_inv.empty:
            raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found.")

        inv_row = match_inv.iloc[0].to_dict()
        cust_id = str(inv_row["customer_id"])

        # Customer profile
        match_cust = cust_df[cust_df["customer_id"] == cust_id]
        if not match_cust.empty:
            c_row = match_cust.iloc[0].to_dict()
            orders = int(c_row.get("orders", 0))
            succ_pmts = int(c_row.get("successful_payments", 0))
            pmt_score = round(succ_pmts / orders, 4) if orders > 0 else 0.5
            cust_profile = CustomerProfile(
                customer_id=cust_id,
                name=str(c_row.get("name", "Customer")),
                segment=str(c_row.get("segment", "normal")),
                ltv=float(c_row.get("ltv", 0.0)),
                orders=orders,
                successful_payments=succ_pmts,
                failed_payments=int(c_row.get("failed_payments", 0)),
                avg_delay_days=float(c_row.get("avg_delay_days", 0.0)),
                customer_score=pmt_score,
            )
        else:
            cust_profile = CustomerProfile(customer_id=cust_id)

        # Recovery score breakdown
        ranked_df = rank_invoices(inv_df, cust_df)
        match_ranked = ranked_df[ranked_df["invoice_id"] == invoice_id]

        if not match_ranked.empty:
            r_row = match_ranked.iloc[0].to_dict()
            score_val = float(r_row["recovery_score"])
            tier_val = classify_tier(score_val)
            breakdown = RecoveryScoreBreakdown(
                recovery_score=score_val,
                tier=tier_val,
                component_scores={
                    "payment_history_score": float(r_row["payment_history_score"]),
                    "promise_history_score": float(r_row["promise_history_score"]),
                    "ltv_score": float(r_row["ltv_score"]),
                    "recency_score": float(r_row["recency_score"]),
                    "response_history_score": float(r_row["response_history_score"]),
                }
            )
        else:
            breakdown = RecoveryScoreBreakdown(
                recovery_score=0.0,
                tier="not_overdue",
                component_scores={}
            )

        actual_rec = float(state_store["recovered_store"].get(invoice_id, 0.0))

        return InvoiceDetailResponse(
            invoice_id=str(inv_row["invoice_id"]),
            customer_id=cust_id,
            amount=float(inv_row["amount"]),
            issue_date=str(inv_row.get("issue_date", "")),
            due_date=str(inv_row.get("due_date", "")),
            days_overdue=int(inv_row.get("days_overdue", 0)),
            status=str(inv_row.get("status", "overdue")),
            actual_recovered=actual_rec,
            customer_profile=cust_profile,
            recovery_score_breakdown=breakdown,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching invoice details: {str(e)}")


@app.get("/invoices/{invoice_id}/audit-trail", tags=["AUDIT-TRAIL"])
def get_invoice_audit_trail(invoice_id: str):
    """
    Returns timestamped append-only audit trail and formatted compact timeline summary for an invoice.
    """
    trail = get_trail(invoice_id)
    summary_text = get_trail_summary(invoice_id)
    return {
        "status": "success",
        "invoice_id": invoice_id,
        "timeline_summary": summary_text,
        "events_count": len(trail),
        "events": [evt.dict() for evt in trail]
    }


# =====================================================================
# 5. POST /recovery/{invoice_id}/recommend
# =====================================================================
@app.post("/recovery/{invoice_id}/recommend", response_model=RecommendResponse, tags=["OFFER-OPTIMIZER"])
def recommend_recovery_offer(invoice_id: str, payload: RecommendRequest):
    """
    Deterministic offer optimization:
    1. Checks recovery_score tier. If 'do_not_chase', halts and returns escalate_to_human.
    2. Runs OFFER-OPTIMIZER + ACCEPT-MODEL to return best_offer & candidate list.
    """
    try:
        if state_store["invoices_df"] is None or state_store["customers_df"] is None:
            load_dataset_state()

        inv_df = state_store["invoices_df"]
        cust_df = state_store["customers_df"]

        match_inv = inv_df[inv_df["invoice_id"] == invoice_id]
        if match_inv.empty:
            raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found.")

        inv_row = match_inv.iloc[0].to_dict()
        invoice_amount = float(inv_row["amount"])
        cust_id = str(inv_row["customer_id"])

        # Check recovery score tier
        ranked_df = rank_invoices(inv_df, cust_df)
        match_ranked = ranked_df[ranked_df["invoice_id"] == invoice_id]

        if not match_ranked.empty:
            rec_score = float(match_ranked.iloc[0]["recovery_score"])
            tier = classify_tier(rec_score)
        else:
            tier = "standard"
            rec_score = 0.5

        # Stopping rule check
        if tier == "do_not_chase":
            return RecommendResponse(
                status="success",
                action="escalate_to_human",
                invoice_id=invoice_id,
                reason=f"Recovery score ({rec_score:.2f}) falls into the 'do_not_chase' tier. Automated recovery halted.",
            )

        # Customer score lookup
        match_cust = cust_df[cust_df["customer_id"] == cust_id]
        if not match_cust.empty:
            c_row = match_cust.iloc[0].to_dict()
            orders = int(c_row.get("orders", 0))
            succ = int(c_row.get("successful_payments", 0))
            cust_score = round(succ / orders, 4) if orders > 0 else 0.5
        else:
            cust_score = 0.5

        model = state_store["accept_model"]
        if model is None:
            raise HTTPException(status_code=500, detail="ACCEPT-MODEL is not loaded.")

        def predict_fn(d_pct: float, days: int, c_score: float, inv_amt: float) -> float:
            return predict_acceptance(model, d_pct, days, c_score, inv_amt)

        opt_result = optimize_offer(
            invoice_amount=invoice_amount,
            merchant_floor=payload.merchant_floor,
            customer_score=cust_score,
            predict_fn=predict_fn
        )

        return RecommendResponse(
            status="success",
            action="recommend_offer",
            invoice_id=invoice_id,
            best_offer=opt_result["best_offer"],
            all_candidates=opt_result["all_candidates"],
            rejected_count=opt_result["rejected_count"],
            valid_count=opt_result["valid_count"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OFFER-OPTIMIZER error: {str(e)}")


# =====================================================================
# 6. POST /recovery/{invoice_id}/execute
# =====================================================================
@app.post("/recovery/{invoice_id}/execute", response_model=ExecuteResponse, tags=["PAY-BRIDGE"])
def execute_recovery_offer(invoice_id: str, payload: ExecuteRequest):
    """
    Calls PAY-BRIDGE to generate a Razorpay payment link and registers pending recovery state.
    """
    try:
        link_data = create_payment_link(invoice_id=invoice_id, amount=payload.offer_amount)

        state_store["executions_store"][invoice_id] = {
            "invoice_id": invoice_id,
            "offer_amount": payload.offer_amount,
            "payment_link_id": link_data["payment_link_id"],
            "payment_link_url": link_data["payment_link_url"],
            "status": "pending_payment",
            "timestamp": time.time()
        }

        return ExecuteResponse(
            status="success",
            invoice_id=invoice_id,
            offer_amount=payload.offer_amount,
            payment_link_id=link_data["payment_link_id"],
            payment_link_url=link_data["payment_link_url"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


# =====================================================================
# 7. POST /webhooks/razorpay
# =====================================================================
@app.post("/webhooks/razorpay", response_model=WebhookResponse, tags=["PAY-BRIDGE Webhook"])
async def razorpay_webhook(request: Request):
    """
    Receives Razorpay payment.captured webhooks, verifies signature, and updates invoice status to 'recovered'.
    """
    try:
        raw_body = await request.body()
        signature = request.headers.get("X-Razorpay-Signature", "")
        webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

        # Verify signature if signature header is provided by Razorpay
        if signature and not verify_webhook_signature(raw_body, signature, webhook_secret):
            raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

        payload = await request.json()
        parsed = parse_webhook_event(payload)

        invoice_id = parsed.get("invoice_id")
        amount = parsed.get("amount_paid", 0.0)

        if invoice_id:
            state_store["recovered_store"][invoice_id] = amount
            
            # Log PAYMENT_CAPTURED event in Audit Trail
            log_event(
                invoice_id=invoice_id,
                event_type="PAYMENT_CAPTURED",
                detail={"amount_paid": amount, "payment_link_id": parsed.get("payment_link_id")},
                actor="webhook"
            )

            # Update status in in-memory DataFrame if present
            if state_store["invoices_df"] is not None:
                mask = state_store["invoices_df"]["invoice_id"] == invoice_id
                state_store["invoices_df"].loc[mask, "status"] = "recovered"

        return WebhookResponse(
            status="processed",
            invoice_id=invoice_id,
            actual_recovered=amount
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


# =====================================================================
# 8. POST /agent/ask
# =====================================================================
@app.post("/agent/ask", response_model=AgentAskResponse, tags=["AGENT-BRAIN"])
def ask_agent(payload: AgentAskRequest):
    """
    Executes AGENT-BRAIN tool-calling loop and returns natural language narration + audit trail log.
    """
    try:
        agent_res = run_agent(payload.message)

        # Infer target invoice_id from message or tool calls if present
        target_inv = None
        for call in agent_res["tool_calls_made"]:
            inp = call.get("input", {})
            if "invoice_id" in inp:
                target_inv = str(inp["invoice_id"])
                break
        
        if target_inv:
            log_from_agent_run(target_inv, agent_res["tool_calls_made"])

        return AgentAskResponse(
            status="success",
            final_response=agent_res["final_response"],
            tool_calls_made=agent_res["tool_calls_made"],
            turns_used=agent_res["turns_used"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AGENT-BRAIN error: {str(e)}")


# =====================================================================
# 9. GET /dashboard/summary
# =====================================================================
@app.get("/dashboard/summary", response_model=DashboardSummaryResponse, tags=["Dashboard"])
def get_dashboard_summary():
    """
    Aggregates top-level metrics:
    - total_revenue_at_risk: sum of overdue invoice amounts + leak impact estimates.
    - total_recoverable: sum of expected_value across high_priority & standard tier invoices.
    - total_actually_recovered: sum of actual_recovered across recovered invoices.
    """
    try:
        if state_store["invoices_df"] is None or state_store["customers_df"] is None:
            load_dataset_state()

        inv_df = state_store["invoices_df"]
        cust_df = state_store["customers_df"]
        txn_df = state_store["transactions_df"]

        # 1. Total revenue at risk
        overdue_mask = inv_df["status"] == "overdue"
        overdue_sum = float(inv_df[overdue_mask]["amount"].sum()) if not inv_df.empty else 0.0

        leaks = scan_all_leaks(txn_df, cust_df) if txn_df is not None else []
        leak_risk = sum(l.get("impact_rupees", 0.0) for l in leaks)

        total_risk = round(overdue_sum + leak_risk, 2)

        # 2. Total recoverable (expected recovery across high_priority & standard invoices)
        ranked_df = rank_invoices(inv_df, cust_df)
        ranked_df["tier"] = ranked_df["recovery_score"].apply(classify_tier)

        recoverable_mask = ranked_df["tier"].isin(["high_priority", "standard"])
        recoverable_df = ranked_df[recoverable_mask]

        if not recoverable_df.empty:
            total_recoverable = float(round((recoverable_df["amount"] * recoverable_df["recovery_score"]).sum(), 2))
        else:
            total_recoverable = 0.0

        # 3. Total actually recovered
        total_recovered = round(sum(state_store["recovered_store"].values()), 2)

        return DashboardSummaryResponse(
            status="success",
            total_revenue_at_risk=total_risk,
            total_recoverable=total_recoverable,
            total_actually_recovered=total_recovered,
            overdue_invoices_count=int(overdue_mask.sum()),
            leaks_detected_count=len(leaks)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard calculation error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
