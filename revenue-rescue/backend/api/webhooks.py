from fastapi import APIRouter, Request, Header, HTTPException
from backend.models.schemas import WebhookResponse
from backend.services.razorpay import verify_webhook_signature, parse_webhook_event
from backend.db.database import log_event

router = APIRouter(prefix="", tags=["PAY-BRIDGE"])

data_store = {}

@router.post("/webhooks/razorpay", response_model=WebhookResponse)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature")
):
    body_bytes = await request.body()

    if x_razorpay_signature:
        is_valid = verify_webhook_signature(body_bytes, x_razorpay_signature)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    payload = await request.json()
    parsed = parse_webhook_event(payload)

    invoice_id = parsed.get("invoice_id")
    amount = parsed.get("amount_paid", 0.0)

    if invoice_id:
        data_store.get("recovered_store", {})[invoice_id] = amount
        log_event(
            invoice_id=invoice_id,
            event_type="PAYMENT_CAPTURED",
            detail={"amount_paid": amount, "payment_link_id": parsed.get("payment_link_id")},
            actor="webhook"
        )

        inv_df = data_store.get("invoices_df")
        if inv_df is not None:
            mask = inv_df["invoice_id"] == invoice_id
            inv_df.loc[mask, "status"] = "recovered"

    return WebhookResponse(
        status="processed",
        invoice_id=invoice_id,
        actual_recovered=amount
    )
