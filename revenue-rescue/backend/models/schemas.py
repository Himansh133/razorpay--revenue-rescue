from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    gemini_configured: bool = False
    active_provider: str = "fallback"
    model: str = "deterministic-engine"

class OpportunityItem(BaseModel):
    opportunity_id: str
    type: str
    title: str
    description: str
    impact_rupees: float
    confidence: float
    segment_details: Dict[str, Any]

class OpportunitiesResponse(BaseModel):
    status: str
    total_leaks: int
    opportunities: List[OpportunityItem]

class InvoiceSummaryItem(BaseModel):
    invoice_id: str
    customer_id: str
    amount: float
    due_date: str
    days_overdue: int
    recovery_score: float
    tier: str

class InvoicesResponse(BaseModel):
    status: str
    tier_filter: Optional[str] = None
    total_count: int
    invoices: List[InvoiceSummaryItem]

class CustomerProfile(BaseModel):
    customer_id: str
    payment_history_score: float = 0.5
    promise_history_score: float = 0.5
    ltv: float = 100000.0
    recency_score: float = 0.5
    response_history_score: float = 0.5

class RecoveryScoreBreakdown(BaseModel):
    recovery_score: float
    tier: str
    component_scores: Dict[str, float]

class InvoiceDetailResponse(BaseModel):
    invoice_id: str
    customer_id: str
    amount: float
    issue_date: str
    due_date: str
    days_overdue: int
    status: str
    actual_recovered: float
    customer_profile: CustomerProfile
    recovery_score_breakdown: RecoveryScoreBreakdown

class RecommendRequest(BaseModel):
    merchant_floor: float = Field(..., description="Absolute minimum acceptable offer amount in ₹")

class CandidateOfferSchema(BaseModel):
    offer_amount: float
    discount_pct: float
    days_to_payment: int
    acceptance_probability: float
    expected_value: float
    is_valid: bool
    rejection_reason: Optional[str] = None

class RecommendResponse(BaseModel):
    invoice_id: str
    original_amount: float
    merchant_floor: float
    best_offer: Optional[CandidateOfferSchema]
    all_candidates: List[CandidateOfferSchema]
    candidates_evaluated: Optional[int] = 70
    selection_reason: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None

class ExecuteRequest(BaseModel):
    offer_amount: float

class ExecuteResponse(BaseModel):
    status: str
    invoice_id: str
    agreed_amount: float
    payment_link_id: str
    payment_link_url: str

class WebhookResponse(BaseModel):
    status: str
    invoice_id: Optional[str] = None
    actual_recovered: float = 0.0

class AgentAskRequest(BaseModel):
    message: str

class AgentAskResponse(BaseModel):
    status: str
    final_response: str
    tool_calls_made: List[Dict[str, Any]]
    turns_used: int
    provider: Optional[str] = None
    model: Optional[str] = None
    is_fallback: bool = False
    fallback_reason: Optional[str] = None

class DashboardSummaryResponse(BaseModel):
    total_revenue_at_risk: float
    total_recoverable: float
    total_actually_recovered: float
    leaks_detected_count: int
    overdue_invoices_count: int
