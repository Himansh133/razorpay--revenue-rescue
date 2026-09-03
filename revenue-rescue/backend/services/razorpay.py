import hmac
import hashlib
import json
import time
import requests
from typing import Dict, Any, Optional
from fastapi import HTTPException
from backend.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET

def create_payment_link(
    invoice_id: str,
    offer_amount: float,
    customer_email: str = "customer@example.com",
    customer_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a real Razorpay Payment Link for the specified recovery offer amount
    using HTTP Basic Authentication with Razorpay Test Mode API.
    
    Converts amount from Rupees (₹) to Paise (1 ₹ = 100 Paise) as integer.
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Razorpay API credentials (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET) are missing."
        )

    amount_in_paise = int(round(offer_amount * 100))

    url = "https://api.razorpay.com/v1/payment_links"
    ref_id = f"{invoice_id}_{int(time.time() * 1000)}"
    payload = {
        "amount": amount_in_paise,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": ref_id,
        "description": f"Revenue recovery for invoice {invoice_id}",
        "customer": {
            "name": customer_name or f"Customer {invoice_id}",
            "email": customer_email,
            "contact": "+919876543210"
        },
        "notify": {
            "sms": False,
            "email": False
        },
        "reminder_enable": True,
        "notes": {
            "invoice_id": str(invoice_id),
            "offer_amount": str(offer_amount)
        }
    }

    try:
        response = requests.post(
            url,
            json=payload,
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to Razorpay API: {str(e)}"
        )

    if response.status_code not in [200, 201]:
        try:
            err_data = response.json()
            err_desc = err_data.get("error", {}).get("description", response.text)
        except Exception:
            err_desc = response.text

        raise HTTPException(
            status_code=response.status_code,
            detail=f"Razorpay API Error ({response.status_code}): {err_desc}"
        )

    res_data = response.json()
    return {
        "id": str(res_data["id"]),
        "entity": "payment_link",
        "amount": float(res_data.get("amount", amount_in_paise)) / 100.0,
        "amount_paid": float(res_data.get("amount_paid", 0)) / 100.0,
        "currency": str(res_data.get("currency", "INR")),
        "status": str(res_data.get("status", "created")),
        "short_url": str(res_data["short_url"]),
        "reference_id": str(res_data.get("reference_id", invoice_id)),
        "notes": res_data.get("notes", {})
    }

def verify_webhook_signature(body_bytes: bytes, signature: str) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    expected_sig = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_sig, signature)

def parse_webhook_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_type = payload.get("event", "")
    plink_entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})

    notes = plink_entity.get("notes", {})
    invoice_id = notes.get("invoice_id")
    amount_paid_paise = plink_entity.get("amount_paid", 0)
    amount_paid_rupees = amount_paid_paise / 100.0

    return {
        "event_type": event_type,
        "payment_link_id": plink_entity.get("id"),
        "invoice_id": invoice_id,
        "amount_paid": amount_paid_rupees,
        "status": plink_entity.get("status")
    }
