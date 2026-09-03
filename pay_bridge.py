"""
PAY-BRIDGE Module: Razorpay Test-Mode Payment Link Integration & Webhook Handler.

Framing Constraint:
-------------------
Money-math (offer amount, concession, expected value) stays completely out of this module.
PAY-BRIDGE takes a final amount (determined by OFFER-OPTIMIZER) and creates a real Razorpay
payment link artifact, verifies webhook signatures, and parses payment capture events.
"""

import os
import sys
import json
import time
import hmac
import hashlib
from datetime import datetime
from typing import Optional, Union, Dict, Any

from dotenv import load_dotenv
from fastapi import HTTPException
import razorpay

# Load environment variables from .env file if present
load_dotenv()


def get_client() -> Optional[razorpay.Client]:
    """
    Initializes and returns the Razorpay SDK client using RAZORPAY_KEY_ID
    and RAZORPAY_KEY_SECRET environment variables.
    Returns None if keys are unconfigured.
    """
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        return None

    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        return client
    except Exception as e:
        print(f"Warning: Failed to initialize Razorpay SDK client: {e}")
        return None


def create_payment_link(
    invoice_id: str,
    amount: float,
    customer_name: Optional[str] = None,
    customer_contact: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Creates a real Razorpay Payment Link for the specified recovery offer amount.
    Uses HTTP Basic Authentication with Razorpay Test Mode API.
    """
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")

    if not key_id or not key_secret:
        raise HTTPException(
            status_code=500,
            detail="Razorpay API credentials (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET) are missing."
        )

    amount_in_paise = int(round(amount * 100))
    ref_id = f"{invoice_id}_{int(time.time())}"

    payload = {
        "amount": amount_in_paise,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": ref_id,
        "description": f"Revenue recovery for invoice {invoice_id}",
        "customer": {
            "name": customer_name or f"Customer {invoice_id}",
            "email": customer_contact.get("email") if customer_contact and "email" in customer_contact else "customer@example.com",
            "contact": "+919876543210"
        },
        "notify": {
            "sms": False,
            "email": False
        },
        "reminder_enable": True,
        "notes": {
            "invoice_id": str(invoice_id),
            "offer_amount": str(amount)
        }
    }

    import requests
    try:
        response = requests.post(
            "https://api.razorpay.com/v1/payment_links",
            json=payload,
            auth=(key_id, key_secret),
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
        "payment_link_id": str(res_data["id"]),
        "payment_link_url": str(res_data["short_url"]),
        "amount": float(res_data.get("amount", amount_in_paise)) / 100.0,
        "status": str(res_data.get("status", "created"))
    }


def verify_webhook_signature(
    payload_body: Union[bytes, str],
    signature_header: str,
    webhook_secret: str
) -> bool:
    """
    Verifies Razorpay HMAC-SHA256 webhook signature.
    Must be called BEFORE trusting any webhook payload.
    
    Returns True if valid signature, False otherwise.
    """
    if not payload_body or not signature_header or not webhook_secret:
        return False

    if isinstance(payload_body, bytes):
        body_bytes = payload_body
        body_str = payload_body.decode("utf-8")
    else:
        body_bytes = payload_body.encode("utf-8")
        body_str = payload_body

    # Primary verification via Razorpay SDK utility
    client = razorpay.Client(auth=("dummy", "dummy"))
    try:
        client.utility.verify_webhook_signature(body_str, signature_header, webhook_secret)
        return True
    except Exception:
        pass

    # Backup HMAC-SHA256 calculation
    try:
        expected_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)
    except Exception:
        return False


def parse_webhook_event(payload: dict) -> Dict[str, Any]:
    """
    Parses and normalizes relevant fields from a verified Razorpay webhook payload.
    
    Extracts invoice_id, payment_link_id, amount_paid (in ₹), event_type, and status.
    """
    event_type = payload.get("event", "payment_link.paid")
    
    invoice_id = None
    payment_link_id = None
    amount_paid_rupees = 0.0
    payment_status = "unknown"
    timestamp = datetime.now().isoformat()

    # Extract entity details from nested payload
    payload_entity = payload.get("payload", {})
    
    payment_link_entity = payload_entity.get("payment_link", {}).get("entity", {})
    payment_entity = payload_entity.get("payment", {}).get("entity", {})

    if payment_link_entity:
        payment_link_id = payment_link_entity.get("id")
        notes = payment_link_entity.get("notes", {})
        invoice_id = notes.get("invoice_id") or payment_link_entity.get("reference_id")
        payment_status = payment_link_entity.get("status", "paid")
        if "amount_paid" in payment_link_entity:
            # Amount converted from paise to Rupees
            amount_paid_rupees = float(payment_link_entity["amount_paid"]) / 100.0

    if payment_entity:
        notes = payment_entity.get("notes", {})
        if not invoice_id:
            invoice_id = notes.get("invoice_id")
        payment_status = payment_entity.get("status", "captured")
        if amount_paid_rupees == 0.0 and "amount" in payment_entity:
            # Amount converted from paise to Rupees
            amount_paid_rupees = float(payment_entity["amount"]) / 100.0

    # Fallback top-level lookups
    if not invoice_id:
        invoice_id = payload.get("invoice_id") or payload.get("reference_id")
    if not payment_link_id:
        payment_link_id = payload.get("payment_link_id")
    if amount_paid_rupees == 0.0 and "amount" in payload:
        amount_paid_rupees = float(payload["amount"])

    return {
        "event_type": event_type,
        "invoice_id": invoice_id,
        "payment_link_id": payment_link_id,
        "amount_paid": amount_paid_rupees,  # in ₹
        "payment_status": payment_status,
        "timestamp": timestamp,
        "raw_payload_event": event_type
    }


def check_payment_link_status(payment_link_id: str) -> Dict[str, Any]:
    """
    Polling fallback: directly checks payment link status via Razorpay API.
    """
    client = get_client()

    if client:
        try:
            resp = client.payment_link.fetch(payment_link_id)
            amount_rupees = float(resp.get("amount", 0.0)) / 100.0
            return {
                "payment_link_id": str(resp.get("id")),
                "status": str(resp.get("status")),
                "amount": amount_rupees,
                "amount_paid": float(resp.get("amount_paid", 0.0)) / 100.0,
                "reference_id": str(resp.get("reference_id", ""))
            }
        except Exception as e:
            print(f"Error fetching payment link '{payment_link_id}': {e}")

    return {
        "payment_link_id": payment_link_id,
        "status": "created",
        "amount": 0.0,
        "amount_paid": 0.0,
        "reference_id": ""
    }


if __name__ == "__main__":
    print("--- DEMO: PAY-BRIDGE STANDALONE EXECUTION & SMOKE TEST ---")

    test_invoice_id = "INV000001"
    test_amount_rupees = 100.0  # ₹100 test offer

    print(f"\n1. Creating Payment Link for Invoice {test_invoice_id} (Amount: ₹{test_amount_rupees:,.2f}):")
    link_info = create_payment_link(
        invoice_id=test_invoice_id,
        amount=test_amount_rupees,
        customer_name="Test Merchant Customer",
        customer_contact={"email": "customer@example.com", "phone": "9999999999"}
    )
    print(f"   Payment Link ID : {link_info['payment_link_id']}")
    print(f"   Payment Link URL: {link_info['payment_link_url']}")
    print(f"   Amount          : ₹{link_info['amount']:,.2f}")
    print(f"   Status          : {link_info['status']}")

    print("\n2. Testing Webhook Signature Verification:")
    secret = "test_webhook_secret_123"
    raw_body = json.dumps({"event": "payment_link.paid", "payload": {"payment_link": {"entity": {"id": link_info["payment_link_id"], "notes": {"invoice_id": test_invoice_id}, "amount_paid": 10000, "status": "paid"}}}}).encode("utf-8")
    
    calc_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    is_valid = verify_webhook_signature(raw_body, calc_sig, secret)
    print(f"   Signature Verification Result: {'VALID ✅' if is_valid else 'INVALID ❌'}")

    print("\n3. Testing Webhook Payload Parsing:")
    parsed_evt = parse_webhook_event(json.loads(raw_body.decode("utf-8")))
    print(f"   Event Type      : {parsed_evt['event_type']}")
    print(f"   Invoice ID      : {parsed_evt['invoice_id']}")
    print(f"   Amount Paid     : ₹{parsed_evt['amount_paid']:,.2f}")
    print(f"   Payment Status  : {parsed_evt['payment_status']}")


"""
Integration Example with API-CORE (main.py):
-------------------------------------------

from pay_bridge import create_payment_link, verify_webhook_signature, parse_webhook_event

# 1. Endpoint /recovery/{invoice_id}/execute
@app.post("/recovery/{invoice_id}/execute")
def execute_recovery(invoice_id: str, offer_amount: float):
    # Call PAY-BRIDGE to construct payment artifact
    link = create_payment_link(invoice_id, amount=offer_amount)
    
    # Store payment link mapping in database / in-memory store
    store_pending_payment(invoice_id, link["payment_link_id"], link["payment_link_url"])
    
    return {
        "status": "success",
        "payment_link_url": link["payment_link_url"],
        "payment_link_id": link["payment_link_id"]
    }

# 2. Endpoint /webhooks/razorpay
@app.post("/webhooks/razorpay")
async def razorpay_webhook_handler(request: Request):
    raw_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "default_secret")
    
    # ALWAYS verify signature before trusting payload
    if not verify_webhook_signature(raw_bytes, signature, webhook_secret):
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")
    
    payload = await request.json()
    parsed = parse_webhook_event(payload)
    
    if parsed["invoice_id"] and parsed["payment_status"] in ["paid", "captured"]:
        # Update invoice status in database
        mark_invoice_as_recovered(parsed["invoice_id"], actual_amount=parsed["amount_paid"])
        
    return {"status": "processed"}
"""
