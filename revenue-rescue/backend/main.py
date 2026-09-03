import os
import pandas as pd
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import DATA_DIR
from backend.models.schemas import (
    HealthResponse,
    AgentAskRequest,
    AgentAskResponse,
    DashboardSummaryResponse
)
from backend.services.analytics import scan_all_leaks
from backend.services.scoring import rank_invoices
from backend.services.optimizer import optimize as optimize_offer
from backend.ml.train import load_model, predict_acceptance
from backend.agents.negotiator import run_negotiator_agent
from backend.db.database import get_trail, get_trail_summary, log_event

from backend.api import opportunities, recovery, webhooks

# Shared in-memory data store
state_store = {
    "transactions_df": None,
    "customers_df": None,
    "invoices_df": None,
    "negotiations_df": None,
    "recovered_store": {},
    "executions_store": {}
}

# Inject data store into routers
opportunities.data_store = state_store
recovery.data_store = state_store
webhooks.data_store = state_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Loading datasets & ML models at startup ---")
    tx_path = Path(DATA_DIR) / "transactions.csv"
    cust_path = Path(DATA_DIR) / "customers.csv"
    inv_path = Path(DATA_DIR) / "invoices.csv"
    neg_path = Path(DATA_DIR) / "negotiations.csv"

    if tx_path.exists():
        state_store["transactions_df"] = pd.read_csv(tx_path)
    if cust_path.exists():
        state_store["customers_df"] = pd.read_csv(cust_path)
    if inv_path.exists():
        state_store["invoices_df"] = pd.read_csv(inv_path)
    if neg_path.exists():
        state_store["negotiations_df"] = pd.read_csv(neg_path)

    try:
        load_model()
    except Exception as e:
        print(f"Warning loading model: {e}")

    yield
    print("--- Shutting down backend ---")

app = FastAPI(
    title="Revenue Rescue API Backend",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(opportunities.router)
app.include_router(recovery.router)
app.include_router(webhooks.router)

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    from backend.config import GEMINI_API_KEY, ANTHROPIC_API_KEY
    gemini_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    anthropic_key = ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")
    
    if gemini_key:
        provider = "gemini"
        model_name = "gemini-3.7-flash"
    elif anthropic_key:
        provider = "anthropic"
        model_name = "claude-3-5-sonnet-20241022"
    else:
        provider = "fallback"
        model_name = "deterministic-engine"

    return HealthResponse(
        status="ok",
        version="1.0.0",
        gemini_configured=bool(gemini_key),
        active_provider=provider,
        model=model_name
    )

@app.get("/invoices/{invoice_id}/audit-trail", tags=["AUDIT-TRAIL"])
def get_invoice_audit_trail(invoice_id: str):
    trail = get_trail(invoice_id)
    summary_text = get_trail_summary(invoice_id)
    return {
        "status": "success",
        "invoice_id": invoice_id,
        "timeline_summary": summary_text,
        "events_count": len(trail),
        "events": [evt.dict() for evt in trail]
    }

@app.post("/agent/ask", response_model=AgentAskResponse, tags=["AGENT-BRAIN"])
def ask_agent(payload: AgentAskRequest):
    try:
        agent_res = run_negotiator_agent(
            payload.message,
            state_store["invoices_df"],
            state_store["customers_df"]
        )
        return AgentAskResponse(
            status="success",
            final_response=agent_res["final_response"],
            tool_calls_made=agent_res["tool_calls_made"],
            turns_used=agent_res["turns_used"],
            provider=agent_res.get("provider"),
            model=agent_res.get("model"),
            is_fallback=agent_res.get("is_fallback", False),
            fallback_reason=agent_res.get("fallback_reason")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AGENT-BRAIN error: {str(e)}")

@app.get("/dashboard/summary", response_model=DashboardSummaryResponse, tags=["Dashboard"])
def get_dashboard_summary():
    tx_df = state_store.get("transactions_df")
    inv_df = state_store.get("invoices_df")
    cust_df = state_store.get("customers_df")

    leaks = scan_all_leaks(tx_df) if tx_df is not None else []
    total_leak_impact = sum(l["impact_rupees"] for l in leaks)

    if inv_df is not None and cust_df is not None:
        ranked_df = rank_invoices(inv_df, cust_df)
        overdue_sum = float(ranked_df["amount"].sum())
        overdue_count = len(ranked_df)

        recoverable = round(overdue_sum * 0.78, 2)
    else:
        overdue_sum = 0.0
        overdue_count = 0
        recoverable = 0.0

    actually_recovered = sum(state_store["recovered_store"].values())

    return DashboardSummaryResponse(
        total_revenue_at_risk=round(overdue_sum + total_leak_impact, 2),
        total_recoverable=round(recoverable, 2),
        total_actually_recovered=round(actually_recovered, 2),
        leaks_detected_count=len(leaks),
        overdue_invoices_count=overdue_count
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
