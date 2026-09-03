"""
Pydantic Data Models for API-CORE (FastAPI Request & Response Schemas)
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


# 1. Health Endpoint
class HealthResponse(BaseModel):
    status: str = Field(default="ok", example="ok")
    data_dir: Optional[str] = Field(default="./output")


# 2. Opportunities Endpoint
class OpportunityItem(BaseModel):
    segment: Any
    baseline_conversion: float
    segment_conversion: float
    z_score: float
    confidence: float
    transactions_count: int
    impact_rupees: float
    title: str


class OpportunitiesResponse(BaseModel):
    status: str = "success"
    total_leaks: int
    opportunities: list[dict]


# 3. Invoices Endpoint
class InvoiceSummaryItem(BaseModel):
    invoice_id: str
    customer_id: str
    amount: float
    days_overdue: int
    recovery_score: float
    tier: str
    payment_history_score: Optional[float] = None
    promise_history_score: Optional[float] = None
    ltv_score: Optional[float] = None
    recency_score: Optional[float] = None
    response_history_score: Optional[float] = None


class InvoicesResponse(BaseModel):
    status: str = "success"
    total_count: int
    invoices: list[InvoiceSummaryItem]


# 4. Invoice Detail Endpoint
class CustomerProfile(BaseModel):
    customer_id: str
    name: Optional[str] = "Customer"
    segment: Optional[str] = "normal"
    ltv: Optional[float] = 0.0
    orders: Optional[int] = 0
    successful_payments: Optional[int] = 0
    failed_payments: Optional[int] = 0
    avg_delay_days: Optional[float] = 0.0
    customer_score: Optional[float] = 0.5


class RecoveryScoreBreakdown(BaseModel):
    recovery_score: float
    tier: str
    component_scores: dict[str, float]


class InvoiceDetailResponse(BaseModel):
    invoice_id: str
    customer_id: str
    amount: float
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    days_overdue: int
    status: str
    actual_recovered: Optional[float] = 0.0
    customer_profile: CustomerProfile
    recovery_score_breakdown: RecoveryScoreBreakdown


# 5. Recommendation Endpoint
class RecommendRequest(BaseModel):
    merchant_floor: float = Field(..., description="Minimum acceptable recovery amount in absolute ₹", example=80000.0)


class RecommendResponse(BaseModel):
    status: str = "success"
    action: str = Field(default="recommend_offer", description="recommend_offer or escalate_to_human")
    invoice_id: str
    reason: Optional[str] = None
    best_offer: Optional[dict] = None
    all_candidates: Optional[list[dict]] = None
    rejected_count: Optional[int] = 0
    valid_count: Optional[int] = 0


# 6. Execute Recovery Endpoint
class ExecuteRequest(BaseModel):
    offer_amount: float = Field(..., description="Agreed offer amount in ₹", example=95000.0)


class ExecuteResponse(BaseModel):
    status: str = "success"
    invoice_id: str
    offer_amount: float
    payment_link_id: str
    payment_link_url: str


# 7. Razorpay Webhook Endpoint
class WebhookResponse(BaseModel):
    status: str = "processed"
    invoice_id: Optional[str] = None
    actual_recovered: Optional[float] = 0.0


# 8. Agent Ask Endpoint
class AgentAskRequest(BaseModel):
    message: str = Field(..., description="Prompt message for AGENT-BRAIN", example="Recover invoice INV000001")


class AgentAskResponse(BaseModel):
    status: str = "success"
    final_response: str
    tool_calls_made: list[dict]
    turns_used: int


# 9. Dashboard Summary Endpoint
class DashboardSummaryResponse(BaseModel):
    status: str = "success"
    total_revenue_at_risk: float
    total_recoverable: float
    total_actually_recovered: float
    overdue_invoices_count: int
    leaks_detected_count: int
