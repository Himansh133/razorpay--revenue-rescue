import os
import pandas as pd
from backend.config import ANTHROPIC_API_KEY
from backend.agents.negotiator import run_negotiator_agent, execute_agent_tool

def run_b5_verification():
    inv_df = pd.read_csv("revenue-rescue/data/invoices.csv")
    cust_df = pd.read_csv("revenue-rescue/data/customers.csv")

    api_key = ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")

    print("==========================================================")
    print("STEP B.5 — VERIFY & HARDEN REAL LLM AGENT")
    print(f"ANTHROPIC_API_KEY present: {bool(api_key)}")
    print("==========================================================")

    # ----------------------------------------------------
    # TEST 1: Recommendation Query (No Payment Link Request)
    # ----------------------------------------------------
    print("\n--- TEST 1: 'What is the best offer for INV001184?' ---")
    res1 = run_negotiator_agent("What is the best offer for INV001184?", inv_df, cust_df)
    tools1 = [t["tool_name"] for t in res1["tool_calls_made"]]
    print("Status:", res1["status"])
    print("Is Fallback:", res1["is_fallback"])
    print("Turns Used:", res1["turns_used"])
    print("Tools Called:", tools1)
    print("create_payment_link called?", "create_payment_link" in tools1)
    assert "create_payment_link" not in tools1, "ERROR: create_payment_link was called when only recommendation was asked!"
    print("✓ Test 1 Passed: create_payment_link was NOT called for analysis request.")

    # ----------------------------------------------------
    # TEST 2: Payment Link Execution Request
    # ----------------------------------------------------
    print("\n--- TEST 2: 'Create the payment link for the recommended offer for INV001184.' ---")
    res2 = run_negotiator_agent("Create the payment link for the recommended offer for INV001184.", inv_df, cust_df)
    tools2 = [t["tool_name"] for t in res2["tool_calls_made"]]
    print("Status:", res2["status"])
    print("Is Fallback:", res2["is_fallback"])
    print("Turns Used:", res2["turns_used"])
    print("Tools Called:", tools2)
    print("create_payment_link called?", "create_payment_link" in tools2)
    assert "create_payment_link" in tools2, "ERROR: create_payment_link was NOT called when user requested link creation!"
    
    # Check Razorpay short url returned
    plink_call = [t for t in res2["tool_calls_made"] if t["tool_name"] == "create_payment_link"][0]
    plink_url = plink_call["result"].get("payment_link_url", "")
    assert plink_url.startswith("http"), f"ERROR: Invalid payment link URL {plink_url}"
    print("Razorpay Payment Link URL:", plink_url)
    print("✓ Test 2 Passed: create_payment_link executed and returned valid Razorpay link.")

    # ----------------------------------------------------
    # TEST 3: General Opportunity Request
    # ----------------------------------------------------
    print("\n--- TEST 3: 'Find the best recovery opportunity for me.' ---")
    res3 = run_negotiator_agent("Find the best recovery opportunity for me.", inv_df, cust_df)
    tools3 = [t["tool_name"] for t in res3["tool_calls_made"]]
    print("Status:", res3["status"])
    print("Is Fallback:", res3["is_fallback"])
    print("Turns Used:", res3["turns_used"])
    print("Tools Called:", tools3)
    assert "create_payment_link" not in tools3, "ERROR: create_payment_link called during general opportunity search!"
    print("✓ Test 3 Passed: General recovery search dynamically selected tool sequence without payment link creation.")

    # ----------------------------------------------------
    # TEST 4: Financial Guardrail Rejection (Below Merchant Floor)
    # ----------------------------------------------------
    print("\n--- TEST 4: Financial Guardrail (Attempt ₹100,000 below merchant floor ₹253,142) ---")
    guard_res = execute_agent_tool("create_payment_link", {"invoice_id": "INV001184", "offer_amount": 100000.0}, inv_df, cust_df)
    print("Guardrail Tool Result:", guard_res)
    assert guard_res.get("status") == "error"
    assert "Financial Guardrail Violation" in guard_res.get("error", "")
    print("✓ Test 4 Passed: Backend strictly rejected ₹100,000 below merchant floor.")

    # ----------------------------------------------------
    # TEST 5: Deterministic Fallback Mode (No API Key)
    # ----------------------------------------------------
    print("\n--- TEST 5: Deterministic Fallback Mode (Simulated No API Key) ---")
    os.environ["ANTHROPIC_API_KEY"] = ""
    res_fb = run_negotiator_agent("What is the best offer for INV001184?", inv_df, cust_df)
    tools_fb = [t["tool_name"] for t in res_fb["tool_calls_made"]]
    print("Status:", res_fb["status"])
    print("Is Fallback:", res_fb["is_fallback"])
    print("Tools Called:", tools_fb)
    assert res_fb["is_fallback"] is True
    assert "create_payment_link" not in tools_fb
    print("✓ Test 5 Passed: Fallback mode executed cleanly with is_fallback=True.")

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    print("\n==========================================================")
    print("ALL STEP B.5 VERIFICATION TESTS PASSED SUCCESSFULLY! 🚀")
    print("==========================================================")

if __name__ == "__main__":
    run_b5_verification()
