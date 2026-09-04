import pandas as pd
from backend.services.optimizer import generate_candidate_offers, optimize
from backend.ml.train import predict_acceptance
from backend.services.razorpay import create_payment_link

def mock_predict_fn(features_dict: dict) -> float:
    discount_pct = features_dict.get("discount_pct", 0)
    days_to_payment = features_dict.get("days_to_payment", 0)
    return round(min(0.50 + (discount_pct * 0.01) + (days_to_payment * 0.003), 0.99), 4)

def test_1_discount_math_5_percent():
    invoice_amount = 269300.0
    discount_pct = 5.0
    expected_offer = invoice_amount * (1.0 - discount_pct / 100.0)
    assert expected_offer == 255835.0

    candidates = generate_candidate_offers(invoice_amount)
    match_5_pct = [c for c in candidates if c[1] == 5.0]
    assert len(match_5_pct) == 7
    for offer_amt, d_pct, _ in match_5_pct:
        assert offer_amt == 255835.0
        assert d_pct == 5.0
    print("✓ Test 1 Passed: 5% discount math is exact (₹2,55,835.00)")

def test_2_all_discount_steps():
    invoice_amount = 269300.0
    candidates = generate_candidate_offers(invoice_amount)
    assert len(candidates) == 70

    expected_discounts = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
    for d in expected_discounts:
        expected_amt = round(invoice_amount * (1.0 - d / 100.0), 2)
        match = [c for c in candidates if c[1] == d]
        assert len(match) == 7
        for offer_amt, d_pct, _ in match:
            assert offer_amt == expected_amt
    print("✓ Test 2 Passed: All 70 candidates generated correctly with exact discount math")

def test_3_floor_enforcement_and_validity():
    invoice_amount = 269300.0
    merchant_floor = 253142.0

    res = optimize(invoice_amount, merchant_floor, mock_predict_fn, {})
    candidates = res["all_candidates"]

    valid_5_pct = [c for c in candidates if c["discount_pct"] == 5.0]
    assert all(c["is_valid"] is True for c in valid_5_pct)

    invalid_10_pct = [c for c in candidates if c["discount_pct"] == 10.0]
    assert all(c["is_valid"] is False for c in invalid_10_pct)
    assert all(c["rejection_reason"].startswith("below_merchant_floor") for c in invalid_10_pct)
    print("✓ Test 3 Passed: Floor enforcement rejects offers below ₹2,53,142.00")

def test_4_exactly_at_floor_is_valid():
    invoice_amount = 100000.0
    merchant_floor = 90000.0

    res = optimize(invoice_amount, merchant_floor, mock_predict_fn, {})
    candidates = res["all_candidates"]

    at_floor_cands = [c for c in candidates if c["offer_amount"] == 90000.0]
    assert len(at_floor_cands) == 7
    assert all(c["is_valid"] is True for c in at_floor_cands)
    print("✓ Test 4 Passed: Offers exactly equal to merchant floor are valid")

def test_5_ev_formula_verification():
    invoice_amount = 269300.0
    merchant_floor = 200000.0

    res = optimize(invoice_amount, merchant_floor, mock_predict_fn, {})
    for c in res["all_candidates"]:
        expected_ev = round(c["offer_amount"] * c["acceptance_probability"], 2)
        assert abs(c["expected_value"] - expected_ev) < 0.01
    print("✓ Test 5 Passed: Expected Value formula EV = offer_amount * probability verified")

def test_6_best_offer_is_highest_ev_valid():
    invoice_amount = 269300.0
    merchant_floor = 253142.0

    res = optimize(invoice_amount, merchant_floor, predict_acceptance, {"customer_score": 0.7411})
    best = res["best_offer"]
    valid_candidates = [c for c in res["all_candidates"] if c["is_valid"]]

    assert best is not None
    assert best["is_valid"] is True
    assert best["offer_amount"] >= merchant_floor
    assert best["offer_amount"] == 255835.0
    assert best["discount_pct"] == 5.0
    assert best["days_to_payment"] == 90

    max_valid_ev = max(c["expected_value"] for c in valid_candidates)
    assert best["expected_value"] == max_valid_ev
    print("✓ Test 6 Passed: Best offer selection correctly selects highest-EV valid offer (₹2,55,835 / 90d)")

def test_7_razorpay_paise_conversion():
    offer_amount = 255835.0
    paise = int(round(offer_amount * 100))
    assert paise == 25583500

    plink_res = create_payment_link("INV001184", offer_amount, "customer@example.com", "Test Customer")
    assert plink_res["status"] == "created"
    assert plink_res["amount"] == 255835.0
    assert int(round(plink_res["amount"] * 100)) == 25583500
    assert plink_res["short_url"].startswith("http")
    print("✓ Test 7 Passed: Razorpay paise conversion (₹2,55,835.00 -> 25583500 paise) and API call verified")

if __name__ == "__main__":
    print("==========================================================")
    print("RUNNING RECOVERY OFFER MATH & OPTIMIZER TEST SUITE")
    print("==========================================================")
    test_1_discount_math_5_percent()
    test_2_all_discount_steps()
    test_3_floor_enforcement_and_validity()
    test_4_exactly_at_floor_is_valid()
    test_5_ev_formula_verification()
    test_6_best_offer_is_highest_ev_valid()
    test_7_razorpay_paise_conversion()
    print("==========================================================")
    print("ALL 7 TESTS PASSED SUCCESSFULLY! 🚀")
    print("==========================================================")
