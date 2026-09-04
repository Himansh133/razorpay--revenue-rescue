import json
import datetime
from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy.orm import Session

from backend.models.schemas import WebhookResponse
from backend.services.razorpay import verify_webhook_signature, parse_webhook_event
from backend.db.database import log_event, SessionLocal, init_db
from backend.db.models import InvoiceModel, PaymentModel, WebhookEventModel

router = APIRouter(prefix="", tags=["PAY-BRIDGE"])

data_store = {}

@router.post("/webhooks/razorpay", response_model=WebhookResponse)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature")
):
    init_db()
    body_bytes = await request.body()

    if x_razorpay_signature:
        is_valid = verify_webhook_signature(body_bytes, x_razorpay_signature)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    payload = await request.json()
    parsed = parse_webhook_event(payload)

    razorpay_event_id = parsed.get("event_id")
    event_type = parsed.get("event_type", "payment_link.paid")
    payment_link_id = parsed.get("payment_link_id")
    invoice_id = parsed.get("invoice_id")
    amount = parsed.get("amount_paid", 0.0)

    db: Session = SessionLocal()
    try:
        # Idempotency Check 1: Webhook Event ID duplicate
        if razorpay_event_id:
            existing_event = db.query(WebhookEventModel).filter(
                WebhookEventModel.razorpay_event_id == razorpay_event_id
            ).first()
            if existing_event:
                return WebhookResponse(
                    status="already_processed",
                    invoice_id=invoice_id,
                    actual_recovered=amount
                )

        # Idempotency Check 2: Payment ID duplicate
        if payment_link_id:
            existing_payment = db.query(PaymentModel).filter(
                PaymentModel.razorpay_payment_id == payment_link_id
            ).first()
            if existing_payment:
                return WebhookResponse(
                    status="already_processed",
                    invoice_id=invoice_id,
                    actual_recovered=amount
                )

        # Process new webhook event
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        if invoice_id:
            invoice = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == invoice_id).first()
            if not invoice:
                invoice = InvoiceModel(
                    invoice_id=invoice_id,
                    customer_id="CUST_UNKNOWN",
                    amount=amount,
                    status="recovered",
                    recovered_amount=amount
                )
                db.add(invoice)
            else:
                invoice.status = "recovered"
                invoice.recovered_amount = amount

            payment = PaymentModel(
                invoice_id=invoice_id,
                razorpay_payment_id=payment_link_id,
                amount=amount,
                status="captured"
            )
            db.add(payment)

            data_store.get("recovered_store", {})[invoice_id] = amount
            inv_df = data_store.get("invoices_df")
            if inv_df is not None:
                mask = inv_df["invoice_id"] == invoice_id
                inv_df.loc[mask, "status"] = "recovered"

        webhook_rec = WebhookEventModel(
            razorpay_event_id=razorpay_event_id,
            event_type=event_type,
            razorpay_payment_id=payment_link_id,
            payload=json.dumps(payload),
            received_at=now_utc,
            processed_at=now_utc,
            status="processed"
        )
        db.add(webhook_rec)
        db.commit()

        if invoice_id:
            log_event(
                invoice_id=invoice_id,
                event_type="PAYMENT_CAPTURED",
                detail={"amount_paid": amount, "payment_link_id": payment_link_id},
                actor="webhook"
            )

        return WebhookResponse(
            status="processed",
            invoice_id=invoice_id,
            actual_recovered=amount
        )
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
