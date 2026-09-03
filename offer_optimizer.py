"""
OFFER-OPTIMIZER Module: Financial Guardrails & Expected-Value Maximization.

Framing & Methodology Constraint:
---------------------------------
No ML or LLM logic lives in this file. This module exists to prove the negotiation engine's
financial guardrails are structural, not advisory.

OFFER-OPTIMIZER generates candidate recovery offers, scores each using ACCEPT-MODEL's
acceptance probability predictions, strictly filters out any candidate below the merchant's
minimum floor, and selects the single offer that maximizes expected revenue.
"""

from typing import Callable, Optional


DEFAULT_DISCOUNT_OPTIONS = [0, 2, 5, 8, 12, 18, 25]  # Discount percentages
DEFAULT_TIMELINE_OPTIONS = [0, 7, 15, 30, 45]          # Payment timeline in days


def generate_candidate_offers(
    invoice_amount: float,
    discount_options: Optional[list[float]] = None,
    timeline_options: Optional[list[int]] = None
) -> list[dict]:
    """
    Generates cross-product candidate offers from discount and timeline options.
    Rounds offer amounts to nearest ₹100 for practical demo presentation.
    
    Returns list of dicts:
    {"discount_pct": float, "days_to_payment": int, "offer_amount": float}
    """
    if discount_options is None:
        discount_options = DEFAULT_DISCOUNT_OPTIONS
    if timeline_options is None:
        timeline_options = DEFAULT_TIMELINE_OPTIONS

    candidates = []
    for discount_pct in discount_options:
        for days in timeline_options:
            raw_amount = invoice_amount * (1.0 - (discount_pct / 100.0))
            # Round to nearest ₹100
            offer_amount = float(round(raw_amount, -2))
            
            candidates.append({
                "discount_pct": float(discount_pct),
                "days_to_payment": int(days),
                "offer_amount": offer_amount,
            })

    return candidates


def score_offers(
    candidates: list[dict],
    invoice_amount: float,
    customer_score: float,
    predict_fn: Callable[[float, int, float, float], float]
) -> list[dict]:
    """
    Scores each candidate offer by calling predict_fn to obtain acceptance_probability,
    and computes expected_value = offer_amount * acceptance_probability.
    
    Returns candidates list with 'acceptance_probability' and 'expected_value' added.
    """
    scored = []
    for c in candidates:
        prob = predict_fn(
            c["discount_pct"],
            c["days_to_payment"],
            customer_score,
            invoice_amount
        )
        prob = float(max(0.0, min(1.0, prob)))
        expected_value = float(round(c["offer_amount"] * prob, 2))

        candidate_scored = c.copy()
        candidate_scored["acceptance_probability"] = round(prob, 4)
        candidate_scored["expected_value"] = expected_value
        scored.append(candidate_scored)

    return scored


def filter_valid_offers(
    scored_candidates: list[dict],
    merchant_floor: float
) -> list[dict]:
    """
    Filters candidates against the hard merchant_floor.
    Tags each candidate with 'is_valid' boolean flag.
    
    Returns list containing ONLY candidates where offer_amount >= merchant_floor.
    """
    valid_candidates = []
    for c in scored_candidates:
        is_valid = c["offer_amount"] >= merchant_floor
        c["is_valid"] = is_valid
        if is_valid:
            valid_candidates.append(c)

    return valid_candidates


def select_best_offer(valid_candidates: list[dict]) -> Optional[dict]:
    """
    Returns the valid candidate offer that maximizes expected_value.
    Returns None if valid_candidates is empty (floor was set too high).
    """
    if not valid_candidates:
        return None

    # Sort by expected_value descending, breaking ties with higher offer_amount
    best = max(valid_candidates, key=lambda c: (c["expected_value"], c["offer_amount"]))
    return best


def optimize(
    invoice_amount: float,
    merchant_floor: float,
    customer_score: float,
    predict_fn: Callable[[float, int, float, float], float],
    discount_options: Optional[list[float]] = None,
    timeline_options: Optional[list[int]] = None
) -> dict:
    """
    Top-level orchestrator:
    1. Generates candidate offers.
    2. Scores candidates via predict_fn and expected value arithmetic.
    3. Filters out invalid candidates below merchant_floor.
    4. Selects single offer maximizing expected value.
    
    Returns dict:
    {
        "best_offer": dict | None,
        "all_candidates": list[dict],
        "rejected_count": int,
        "valid_count": int,
    }
    """
    candidates = generate_candidate_offers(invoice_amount, discount_options, timeline_options)
    scored_candidates = score_offers(candidates, invoice_amount, customer_score, predict_fn)
    valid_candidates = filter_valid_offers(scored_candidates, merchant_floor)
    best_offer = select_best_offer(valid_candidates)

    rejected_count = len(scored_candidates) - len(valid_candidates)
    valid_count = len(valid_candidates)

    return {
        "best_offer": best_offer,
        "all_candidates": scored_candidates,
        "rejected_count": rejected_count,
        "valid_count": valid_count,
    }


if __name__ == "__main__":
    print("--- DEMO: OFFER-OPTIMIZER STANDALONE EXECUTION ---")

    # Mock predict_fn simulating plausible acceptance probability curve
    def fake_predict(discount_pct: float, days_to_payment: int, customer_score: float, invoice_amount: float) -> float:
        base_prob = 0.45
        discount_boost = (discount_pct / 100.0) * 1.8
        timeline_boost = (days_to_payment / 45.0) * 0.15
        customer_boost = (customer_score - 0.5) * 0.4
        return min(0.98, max(0.05, base_prob + discount_boost + timeline_boost + customer_boost))

    demo_invoice_amount = 100000.0
    demo_merchant_floor = 85000.0
    demo_customer_score = 0.75

    print(f"\nScenario Context:")
    print(f"  Invoice Amount : ₹{demo_invoice_amount:,.2f}")
    print(f"  Merchant Floor : ₹{demo_merchant_floor:,.2f}")
    print(f"  Customer Score : {demo_customer_score}")

    result = optimize(
        invoice_amount=demo_invoice_amount,
        merchant_floor=demo_merchant_floor,
        customer_score=demo_customer_score,
        predict_fn=fake_predict
    )

    print(f"\nEvaluated {len(result['all_candidates'])} Candidate Offers:")
    print(f"  Valid Offers   : {result['valid_count']}")
    print(f"  Rejected Offers: {result['rejected_count']} (Below ₹{demo_merchant_floor:,.2f} floor)")

    print("\n--- SAMPLE CANDIDATE OFFERS TABLE ---")
    headers = f"{'Discount %':<12} {'Timeline':<10} {'Offer Amount':<14} {'Accept Prob':<14} {'Expected Val':<14} {'Status':<15}"
    print(headers)
    print("-" * len(headers))

    for c in result["all_candidates"]:
        status = "VALID" if c["is_valid"] else "❌ REJECTED (Below Floor)"
        print(f"{c['discount_pct']:<12.1f} {c['days_to_payment']:<10} ₹{c['offer_amount']:<13,.0f} {c['acceptance_probability']:<14.1%} ₹{c['expected_value']:<13,.2f} {status:<15}")

    print("\n--- RECOMMENDED BEST OFFER ---")
    best = result["best_offer"]
    if best:
        print(f"  Optimal Offer Amount  : ₹{best['offer_amount']:,.2f} ({best['discount_pct']}% discount)")
        print(f"  Payment Timeline      : {best['days_to_payment']} days")
        print(f"  Acceptance Probability: {best['acceptance_probability']:.1%}")
        print(f"  Expected Revenue      : ₹{best['expected_value']:,.2f}")
    else:
        print("  No valid offer could be generated above the merchant floor.")


"""
Integration Example with AGENT-BRAIN (LLM Agent / API Layer):
-----------------------------------------------------------

from offer_optimizer import optimize
from accept_model import load_model, predict_acceptance

# 1. Load ML model once at startup
accept_model_obj = load_model("./output/accept_model.joblib")

# 2. Dependency-injected prediction function
def model_predict_fn(discount_pct, days_to_payment, customer_score, invoice_amount):
    return predict_acceptance(accept_model_obj, discount_pct, days_to_payment, customer_score, invoice_amount)

# 3. Execute optimization when user/merchant requests recovery strategy
result = optimize(
    invoice_amount=100000.0,
    merchant_floor=85000.0,
    customer_score=0.75,
    predict_fn=model_predict_fn
)

best_offer = result["best_offer"]
rejected_offers = [c for c in result["all_candidates"] if not c["is_valid"]]

# 4. Natural Language Response Construction for AGENT-BRAIN:
if best_offer:
    explanation = (
        f"I evaluated {len(result['all_candidates'])} possible offer variations. "
        f"The optimal recommendation is a {best_offer['discount_pct']}% discount (₹{best_offer['offer_amount']:,.2f}) "
        f"with a {best_offer['days_to_payment']}-day payment timeline. "
        f"This yields a predicted acceptance rate of {best_offer['acceptance_probability']:.1%} "
        f"and maximizes your expected revenue at ₹{best_offer['expected_value']:,.2f}.\n\n"
        f"Note: {result['rejected_count']} aggressive discount candidates (e.g. 18% and 25% discounts) "
        f"were automatically REJECTED because they fell below your hard merchant floor of ₹85,000."
    )
else:
    explanation = (
        f"No valid offer could be generated. All evaluated discount options fell below your "
        f"merchant floor of ₹85,000. Consider lowering your floor to enable recovery offers."
    )

print(explanation)
"""
