import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.agents.negotiator import AGENT_TOOLS, execute_agent_tool, run_negotiator_agent, MAX_TOOL_ITERATIONS
from backend.services.razorpay import create_payment_link
from backend.config import DATA_DIR

def get_sample_data():
    inv_path = os.path.join(DATA_DIR, "invoices.csv") if os.path.exists(os.path.join(DATA_DIR, "invoices.csv")) else "data/invoices.csv"
    cust_path = os.path.join(DATA_DIR, "customers.csv") if os.path.exists(os.path.join(DATA_DIR, "customers.csv")) else "data/customers.csv"
    inv_df = pd.read_csv(inv_path)
    cust_df = pd.read_csv(cust_path)
    return inv_df, cust_df

@pytest.fixture
def sample_data():
    return get_sample_data()

def test_1_tool_schemas_validity():
    assert len(AGENT_TOOLS) == 5
    tool_names = [t["name"] for t in AGENT_TOOLS]
    assert "rank_invoices" in tool_names
    assert "get_customer_profile" in tool_names
    assert "optimize_offer" in tool_names
    assert "create_payment_link" in tool_names
    assert "send_recovery_message" in tool_names

    for tool in AGENT_TOOLS:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
    print("✓ Test 1 Passed: Tool schemas are valid")

def test_2_known_tool_execution(sample_data):
    inv_df, cust_df = sample_data
    res = execute_agent_tool("rank_invoices", {"min_tier": "high_priority"}, inv_df, cust_df)
    assert "top_invoices" in res
    assert "total_ranked" in res
    assert len(res["top_invoices"]) > 0
    print("✓ Test 2 Passed: Known tool 'rank_invoices' executes correctly")

def test_3_tool_result_structure(sample_data):
    inv_df, cust_df = sample_data
    res = execute_agent_tool("optimize_offer", {"invoice_id": "INV001184"}, inv_df, cust_df)
    assert res["invoice_id"] == "INV001184"
    assert res["invoice_amount"] == 269300.0
    assert res["merchant_floor"] == 253142.0
    assert res["candidates_evaluated"] == 70
    assert res["best_offer"]["offer_amount"] == 255835.0
    assert res["best_offer"]["discount_pct"] == 5.0
    assert res["best_offer"]["days_to_payment"] == 90
    print("✓ Test 3 Passed: Tool result structure for optimize_offer is correct")

def test_4_unknown_tool_rejection(sample_data):
    inv_df, cust_df = sample_data
    res = execute_agent_tool("unknown_fake_tool", {}, inv_df, cust_df)
    assert "error" in res
    assert "Unknown tool" in res["error"]
    print("✓ Test 4 Passed: Unknown tool is safely rejected")

def test_5_max_iteration_limit():
    assert MAX_TOOL_ITERATIONS == 8
    print("✓ Test 5 Passed: Maximum tool iteration limit is configured to 8")

def test_6_missing_api_key_fallback(sample_data, monkeypatch):
    inv_df, cust_df = sample_data
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    res = run_negotiator_agent("What is the best offer for INV001184?", inv_df, cust_df)
    assert res["status"] == "success"
    assert res["is_fallback"] is True
    assert len(res["tool_calls_made"]) > 0
    assert "INV001184" in res["final_response"]
    print("✓ Test 6 Passed: Missing API key triggers safe deterministic fallback mode")

def test_7_optimize_offer_financial_values_deterministic(sample_data):
    inv_df, cust_df = sample_data
    res1 = execute_agent_tool("optimize_offer", {"invoice_id": "INV001184"}, inv_df, cust_df)
    res2 = execute_agent_tool("optimize_offer", {"invoice_id": "INV001184"}, inv_df, cust_df)
    assert res1["best_offer"] == res2["best_offer"]
    assert res1["merchant_floor"] == res2["merchant_floor"] == 253142.0
    print("✓ Test 7 Passed: Financial calculations remain strictly deterministic")

def test_8_create_payment_link_floor_guardrail_rejection(sample_data):
    inv_df, cust_df = sample_data
    # Attempt to create payment link for ₹1,00,000 (well below floor ₹2,53,142)
    res = execute_agent_tool("create_payment_link", {"invoice_id": "INV001184", "offer_amount": 100000.0}, inv_df, cust_df)
    assert res["status"] == "error"
    assert "Financial Guardrail Violation" in res["error"]
    assert "253,142.00" in res["error"]
    print("✓ Test 8 Passed: Payment link creation strictly rejects amounts below merchant floor")

def test_9_create_payment_link_valid_amount(sample_data):
    from backend.api.recovery import data_store
    data_store["executions_store"] = {}
    inv_df, cust_df = sample_data
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "plink_test_999",
        "amount": 25583500,
        "status": "created",
        "short_url": "https://rzp.io/l/valid_test_link"
    }

    with patch("requests.post", return_value=mock_resp):
        res = execute_agent_tool("create_payment_link", {"invoice_id": "INV001184", "offer_amount": 255835.0}, inv_df, cust_df)
        assert res["status"] == "success"
        assert res["agreed_amount"] == 255835.0
        assert res["payment_link_url"].startswith("https://")
    print("✓ Test 9 Passed: Valid offer amount successfully generates payment link")

def test_10_razorpay_error_handling_no_demo_links(sample_data):
    from backend.api.recovery import data_store
    data_store["executions_store"] = {}
    inv_df, cust_df = sample_data
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.text = "Unauthorized"
    mock_401.json.return_value = {"error": {"description": "Invalid key"}}

    with patch("requests.post", return_value=mock_401):
        res = execute_agent_tool("create_payment_link", {"invoice_id": "INV001184", "offer_amount": 255835.0}, inv_df, cust_df)
        assert res["status"] == "error"
        assert "Razorpay API Error" in res["error"]
        assert "rzp.io/rzp/demo_" not in str(res)
    print("✓ Test 10 Passed: Agent create_payment_link tool returns status error on Razorpay API failures (no demo links)")

if __name__ == "__main__":
    print("==========================================================")
    print("RUNNING LLM TOOL-CALLING AGENT TEST SUITE")
    print("==========================================================")
    inv_df, cust_df = get_sample_data()
    sd = (inv_df, cust_df)

    test_1_tool_schemas_validity()
    test_2_known_tool_execution(sd)
    test_3_tool_result_structure(sd)
    test_4_unknown_tool_rejection(sd)
    test_5_max_iteration_limit()
    class MonkeyPatch:
        def setenv(self, k, v): os.environ[k] = v
    test_6_missing_api_key_fallback(sd, MonkeyPatch())
    test_7_optimize_offer_financial_values_deterministic(sd)
    test_8_create_payment_link_floor_guardrail_rejection(sd)
    test_9_create_payment_link_valid_amount(sd)
    test_10_razorpay_error_handling_no_demo_links(sd)
    print("==========================================================")
    print("ALL 10 AGENT TESTS PASSED SUCCESSFULLY! 🚀")
    print("==========================================================")
