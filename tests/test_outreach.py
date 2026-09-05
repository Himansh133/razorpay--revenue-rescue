import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.outreach import send_recovery_email, send_recovery_sms
from backend.agents.negotiator import execute_agent_tool, run_deterministic_fallback
from backend.api.recovery import data_store

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_data():
    invoices_data = [
        {"invoice_id": "INV001974", "customer_id": "CUST000001", "amount": 50000.0, "status": "overdue", "due_date": "2026-08-01", "days_overdue": 35}
    ]
    customers_data = [
        {"customer_id": "CUST000001", "name": "Aman Kapoor", "email": "aman@example.com", "phone": "+919876543210", "company": "Kapoor Logistics", "segment": "normal", "ltv": 150000.0, "total_invoices_count": 10, "successful_payments_count": 8, "promises_made_count": 2, "promises_kept_count": 2, "emails_sent_count": 5, "emails_opened_count": 4}
    ]
    data_store["invoices_df"] = pd.DataFrame(invoices_data)
    data_store["customers_df"] = pd.DataFrame(customers_data)
    data_store["executions_store"] = {}


def test_send_recovery_email_missing_contact():
    res = send_recovery_email(
        invoice_id="INV001974",
        customer_id="CUST000001",
        customer_name="Aman Kapoor",
        recipient_email="",
        original_amount=50000.0,
        offer_amount=47000.0,
        discount_pct=6.0,
        payment_terms_days=90,
        payment_url="https://rzp.io/rzp/test_link"
    )
    assert res["status"] == "unavailable"
    assert "missing or invalid" in res["error"]


def test_send_recovery_sms_missing_contact():
    res = send_recovery_sms(
        invoice_id="INV001974",
        customer_id="CUST000001",
        recipient_phone="",
        offer_amount=47000.0,
        payment_url="https://rzp.io/rzp/test_link"
    )
    assert res["status"] == "unavailable"
    assert "missing or invalid" in res["error"]


def test_outreach_api_endpoint():
    with patch("backend.api.recovery.create_payment_link") as mock_plink:
        mock_plink.return_value = {
            "id": "plink_test123",
            "short_url": "https://rzp.io/rzp/test123"
        }

        res = client.post("/recovery/INV001974/outreach", json={
            "channels": ["email", "sms"],
            "merchant_floor": 47000.0
        })

        assert res.status_code == 200
        data = res.json()
        assert data["invoice_id"] == "INV001974"
        assert data["payment_link_id"] == "plink_test123"
        assert data["payment_link_url"] == "https://rzp.io/rzp/test123"
        assert "email" in data["channels"]
        assert "sms" in data["channels"]


def test_agent_outreach_tool_order_guardrail():
    inv_df = data_store["invoices_df"]
    cust_df = data_store["customers_df"]

    # Fails if payment link does not exist
    data_store["executions_store"] = {}
    err_res = execute_agent_tool("send_recovery_message", {"invoice_id": "INV001974"}, inv_df, cust_df)
    assert err_res["status"] == "error"
    assert "Agent Order Guardrail Violation" in err_res["error"]

    # Succeeds if payment link exists
    data_store["executions_store"]["INV001974"] = {
        "agreed_amount": 47000.0,
        "payment_link_id": "plink_existing",
        "payment_link_url": "https://rzp.io/rzp/existing"
    }

    succ_res = execute_agent_tool("send_recovery_message", {"invoice_id": "INV001974"}, inv_df, cust_df)
    assert succ_res["status"] == "success"
    assert succ_res["payment_link_url"] == "https://rzp.io/rzp/existing"
    assert "email" in succ_res["channels"]
    assert "sms" in succ_res["channels"]


def test_deterministic_fallback_with_outreach():
    inv_df = data_store["invoices_df"]
    cust_df = data_store["customers_df"]

    with patch("backend.agents.negotiator.create_payment_link") as mock_plink:
        mock_plink.return_value = {
            "id": "plink_fallback_outreach",
            "short_url": "https://rzp.io/rzp/fallback_outreach"
        }

        res = run_deterministic_fallback(
            user_message="Send recovery offer to customer for invoice INV001974 via email and sms",
            invoices_df=inv_df,
            customers_df=cust_df
        )

        assert res["status"] == "success"
        assert res["is_fallback"] is True
        tools = [t["tool_name"] for t in res["tool_calls_made"]]
        assert "rank_invoices" in tools
        assert "get_customer_profile" in tools
        assert "optimize_offer" in tools
        assert "create_payment_link" in tools
        assert "send_recovery_message" in tools
