from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from backend.models.schemas import (
    InvoicesResponse,
    InvoiceSummaryItem,
    InvoiceDetailResponse,
    CustomerProfile,
    RecoveryScoreBreakdown,
    RecommendRequest,
    RecommendResponse,
    ExecuteRequest,
    ExecuteResponse,
    OutreachRequest,
    OutreachResponse,
    OutreachChannelDetail
)
from backend.services.scoring import rank_invoices, classify_tier
from backend.services.optimizer import optimize as optimize_offer
from backend.ml.train import predict_acceptance
from backend.services.razorpay import create_payment_link
from backend.services.outreach import send_recovery_email, send_recovery_sms
from backend.db.database import log_event

router = APIRouter(prefix="", tags=["RECOVERY & OPTIMIZER"])

data_store = {}

@router.get("/invoices", response_model=InvoicesResponse)
def list_overdue_invoices(
    tier: Optional[str] = Query(None, description="Filter by tier: high_priority, standard, low_priority, do_not_contact"),
    min_amount: float = Query(0.0, ge=0.0)
):
    inv_df = data_store.get("invoices_df")
    cust_df = data_store.get("customers_df")
    if inv_df is None or cust_df is None:
        raise HTTPException(status_code=500, detail="Invoice or Customer data not loaded")

    ranked_df = rank_invoices(inv_df, cust_df)
    if ranked_df.empty:
        return InvoicesResponse(status="success", tier_filter=tier, total_count=0, invoices=[])

    filtered = ranked_df[ranked_df["amount"] >= min_amount]
    if tier:
        filtered = filtered[filtered["tier"] == tier]

    summary_items = []
    for _, row in filtered.iterrows():
        summary_items.append(InvoiceSummaryItem(
            invoice_id=str(row["invoice_id"]),
            customer_id=str(row["customer_id"]),
            amount=float(row["amount"]),
            due_date=str(row.get("due_date", "")),
            days_overdue=int(row.get("days_overdue", 0)),
            recovery_score=float(row["recovery_score"]),
            tier=str(row["tier"])
        ))

    return InvoicesResponse(
        status="success",
        tier_filter=tier,
        total_count=len(summary_items),
        invoices=summary_items
    )

@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice_detail(invoice_id: str):
    inv_df = data_store.get("invoices_df")
    cust_df = data_store.get("customers_df")
    if inv_df is None or cust_df is None:
        raise HTTPException(status_code=500, detail="Data files not loaded")

    match_inv = inv_df[inv_df["invoice_id"] == invoice_id]
    if match_inv.empty:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found")

    inv_row = match_inv.iloc[0].to_dict()
    cust_id = str(inv_row["customer_id"])

    match_cust = cust_df[cust_df["customer_id"] == cust_id]
    if not match_cust.empty:
        c_row = match_cust.iloc[0].to_dict()
        tot_inv = float(c_row.get("total_invoices_count", 1))
        succ_pay = float(c_row.get("successful_payments_count", 0))
        prom_made = float(c_row.get("promises_made_count", 1))
        prom_kept = float(c_row.get("promises_kept_count", 0))
        em_sent = float(c_row.get("emails_sent_count", 1))
        em_open = float(c_row.get("emails_opened_count", 0))

        cust_profile = CustomerProfile(
            customer_id=cust_id,
            payment_history_score=round(succ_pay / max(1.0, tot_inv), 4),
            promise_history_score=round(prom_kept / max(1.0, prom_made), 4),
            ltv=float(c_row.get("ltv", 100000.0)),
            recency_score=0.75,
            response_history_score=round(em_open / max(1.0, em_sent), 4)
        )
    else:
        cust_profile = CustomerProfile(customer_id=cust_id)

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
        breakdown = RecoveryScoreBreakdown(recovery_score=0.0, tier="not_overdue", component_scores={})

    from backend.db.database import SessionLocal
    from backend.db.models import InvoiceModel

    db = SessionLocal()
    try:
        inv_db = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == invoice_id).first()
        status_val = inv_db.status if inv_db else str(inv_row.get("status", "overdue"))
        actual_rec = inv_db.recovered_amount if inv_db else float(data_store.get("recovered_store", {}).get(invoice_id, 0.0))
    finally:
        db.close()

    return InvoiceDetailResponse(
        invoice_id=str(inv_row["invoice_id"]),
        customer_id=cust_id,
        amount=float(inv_row["amount"]),
        issue_date=str(inv_row.get("issue_date", "")),
        due_date=str(inv_row.get("due_date", "")),
        days_overdue=int(inv_row.get("days_overdue", 0)),
        status=status_val,
        actual_recovered=actual_rec,
        customer_profile=cust_profile,
        recovery_score_breakdown=breakdown
    )

@router.post("/recovery/{invoice_id}/recommend", response_model=RecommendResponse)
def recommend_recovery_offer(invoice_id: str, payload: RecommendRequest):
    detail = get_invoice_detail(invoice_id)
    cust_profile = detail.customer_profile

    cust_features = {
        "customer_score": detail.recovery_score_breakdown.recovery_score,
        "payment_history_score": cust_profile.payment_history_score,
        "promise_history_score": cust_profile.promise_history_score,
        "ltv": cust_profile.ltv,
        "recency_score": cust_profile.recency_score,
        "response_history_score": cust_profile.response_history_score,
    }

    res = optimize_offer(
        invoice_amount=detail.amount,
        merchant_floor=payload.merchant_floor,
        predict_fn=predict_acceptance,
        customer_features=cust_features
    )

    log_event(invoice_id, "OFFERS_EVALUATED", {"candidates_count": len(res["all_candidates"])})
    if res.get("best_offer"):
        log_event(invoice_id, "OFFER_SELECTED", res["best_offer"])

    return RecommendResponse(
        invoice_id=invoice_id,
        original_amount=res["original_amount"],
        merchant_floor=res["merchant_floor"],
        best_offer=res["best_offer"],
        all_candidates=res["all_candidates"],
        candidates_evaluated=res.get("candidates_evaluated", len(res["all_candidates"])),
        selection_reason=res.get("selection_reason"),
        constraints=res.get("constraints")
    )

@router.post("/recovery/{invoice_id}/execute", response_model=ExecuteResponse)
def execute_recovery_offer(invoice_id: str, payload: ExecuteRequest):
    detail = get_invoice_detail(invoice_id)

    # Check if a valid payment link already exists
    executions_store = data_store.setdefault("executions_store", {})
    existing = executions_store.get(invoice_id)
    if existing and existing.get("payment_link_url"):
        return ExecuteResponse(
            status="success",
            invoice_id=invoice_id,
            agreed_amount=existing.get("agreed_amount", payload.offer_amount),
            payment_link_id=existing["payment_link_id"],
            payment_link_url=existing["payment_link_url"]
        )

    plink_res = create_payment_link(
        invoice_id=invoice_id,
        offer_amount=payload.offer_amount,
        customer_email=f"{detail.customer_id.lower()}@example.com",
        customer_name=detail.customer_id
    )

    executions_store[invoice_id] = {
        "agreed_amount": payload.offer_amount,
        "payment_link_id": plink_res["id"],
        "payment_link_url": plink_res["short_url"]
    }

    log_event(invoice_id, "PAYMENT_LINK_CREATED", {"amount": payload.offer_amount, "link_id": plink_res["id"]})

    return ExecuteResponse(
        status="success",
        invoice_id=invoice_id,
        agreed_amount=payload.offer_amount,
        payment_link_id=plink_res["id"],
        payment_link_url=plink_res["short_url"]
    )

@router.post("/recovery/{invoice_id}/outreach", response_model=OutreachResponse)
def execute_customer_outreach(invoice_id: str, payload: OutreachRequest):
    detail = get_invoice_detail(invoice_id)
    cust_id = detail.customer_id

    executions_store = data_store.setdefault("executions_store", {})
    existing_exec = executions_store.get(invoice_id)

    offer_amt = payload.offer_amount
    payment_link_id = None
    payment_link_url = None

    if existing_exec and existing_exec.get("payment_link_url"):
        payment_link_id = existing_exec["payment_link_id"]
        payment_link_url = existing_exec["payment_link_url"]
        offer_amt = offer_amt or existing_exec.get("agreed_amount", round(detail.amount * 0.95, 2))
    else:
        if not offer_amt:
            floor = payload.merchant_floor if payload.merchant_floor is not None else float(round(detail.amount * 0.94))
            rec_res = recommend_recovery_offer(invoice_id, RecommendRequest(merchant_floor=floor))
            best = rec_res.best_offer
            offer_amt = best.offer_amount if best else floor

        try:
            plink_res = create_payment_link(
                invoice_id=invoice_id,
                offer_amount=offer_amt,
                customer_email=f"{cust_id.lower()}@example.com",
                customer_name=f"Customer {cust_id}"
            )
            payment_link_id = plink_res["id"]
            payment_link_url = plink_res["short_url"]
            executions_store[invoice_id] = {
                "agreed_amount": offer_amt,
                "payment_link_id": payment_link_id,
                "payment_link_url": payment_link_url
            }
            log_event(invoice_id, "PAYMENT_LINK_CREATED", {"amount": offer_amt, "link_id": payment_link_id})
        except HTTPException as he:
            err_detail = str(he.detail)
            log_event(invoice_id, "OUTREACH_FAILED", {"reason": err_detail})
            raise HTTPException(
                status_code=he.status_code,
                detail=f"Customer outreach could not be sent because a Razorpay payment link could not be created. {err_detail}"
            )
        except Exception as e:
            err_detail = str(e)
            log_event(invoice_id, "OUTREACH_FAILED", {"reason": err_detail})
            raise HTTPException(
                status_code=500,
                detail=f"Customer outreach could not be sent because a Razorpay payment link could not be created. {err_detail}"
            )

    discount_pct = round(((detail.amount - offer_amt) / detail.amount) * 100.0, 1) if detail.amount > 0 else 0.0
    terms_days = 90

    cust_df = data_store.get("customers_df")
    cust_name = cust_id
    cust_email = f"{cust_id.lower()}@example.com"
    cust_phone = "+919876543210"

    if cust_df is not None:
        m_cust = cust_df[cust_df["customer_id"] == cust_id]
        if not m_cust.empty:
            c_row = m_cust.iloc[0].to_dict()
            cust_name = str(c_row.get("name") or c_row.get("company") or cust_id)
            if c_row.get("email"):
                cust_email = str(c_row.get("email"))
            if c_row.get("phone"):
                cust_phone = str(c_row.get("phone"))

    channel_results = {}
    requested_channels = payload.channels or ["email", "sms"]

    if "email" in requested_channels:
        email_res = send_recovery_email(
            invoice_id=invoice_id,
            customer_id=cust_id,
            customer_name=cust_name,
            recipient_email=cust_email,
            original_amount=detail.amount,
            offer_amount=offer_amt,
            discount_pct=discount_pct,
            payment_terms_days=terms_days,
            payment_url=payment_link_url
        )
        channel_results["email"] = OutreachChannelDetail(
            status=email_res["status"],
            recipient=email_res.get("recipient"),
            provider=email_res.get("provider"),
            message_id=email_res.get("message_id"),
            error=email_res.get("error")
        )

    if "sms" in requested_channels:
        sms_res = send_recovery_sms(
            invoice_id=invoice_id,
            customer_id=cust_id,
            recipient_phone=cust_phone,
            offer_amount=offer_amt,
            payment_url=payment_link_url
        )
        channel_results["sms"] = OutreachChannelDetail(
            status=sms_res["status"],
            recipient=sms_res.get("recipient"),
            provider=sms_res.get("provider"),
            message_id=sms_res.get("message_id"),
            error=sms_res.get("error")
        )

    statuses = [c.status for c in channel_results.values()]
    if all(s in ["sent", "already_sent"] for s in statuses):
        overall = "success"
    elif any(s in ["sent", "already_sent"] for s in statuses):
        overall = "partial_success"
    else:
        overall = "failed"

    return OutreachResponse(
        status=overall,
        invoice_id=invoice_id,
        payment_link_id=payment_link_id,
        payment_link_url=payment_link_url,
        channels=channel_results
    )
