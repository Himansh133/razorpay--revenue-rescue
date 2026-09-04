from typing import List, Dict, Any, Tuple, Optional

DISCOUNT_STEPS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
PAYMENT_TERM_STEPS = [0, 7, 14, 30, 45, 60, 90]

def generate_candidate_offers(invoice_amount: float) -> List[Tuple[float, float, int]]:
    candidates = []
    for d in DISCOUNT_STEPS:
        for t in PAYMENT_TERM_STEPS:
            offer_amount = round(invoice_amount * (1.0 - d), 2)
            discount_pct = round(d * 100, 1)
            candidates.append((offer_amount, discount_pct, t))
    return candidates

def optimize(
    invoice_amount: float,
    merchant_floor: float,
    predict_fn,
    customer_features: Dict[str, Any]
) -> Dict[str, Any]:
    candidates = generate_candidate_offers(invoice_amount)
    all_evaluated = []
    best_offer = None
    max_ev = -1.0

    for offer_amount, discount_pct, days_to_payment in candidates:
        features = {
            **customer_features,
            "invoice_amount": invoice_amount,
            "offer_amount": offer_amount,
            "discount_pct": discount_pct,
            "days_to_payment": days_to_payment,
        }

        prob = predict_fn(features)
        ev = round(prob * offer_amount, 2)
        is_valid = offer_amount >= merchant_floor
        rejection_reason = None if is_valid else f"below_merchant_floor (Floor: ₹{merchant_floor:,.2f})"

        candidate_obj = {
            "offer_amount": offer_amount,
            "discount_pct": discount_pct,
            "days_to_payment": days_to_payment,
            "acceptance_probability": round(prob, 4),
            "expected_value": ev,
            "is_valid": is_valid,
            "rejection_reason": rejection_reason
        }

        all_evaluated.append(candidate_obj)

        if is_valid and ev > max_ev:
            max_ev = ev
            best_offer = candidate_obj

    selection_reason = (
        f"Selected offer ₹{best_offer['offer_amount']:,.2f} ({best_offer['discount_pct']}% discount, "
        f"{best_offer['days_to_payment']}-day payment terms) yielding highest Expected Value "
        f"₹{best_offer['expected_value']:,.2f} among valid offers meeting merchant floor ₹{merchant_floor:,.2f}."
    ) if best_offer else f"No candidate offer satisfied the merchant floor constraint of ₹{merchant_floor:,.2f}."

    return {
        "original_amount": invoice_amount,
        "merchant_floor": merchant_floor,
        "best_offer": best_offer,
        "all_candidates": all_evaluated,
        "candidates_evaluated": len(all_evaluated),
        "selection_reason": selection_reason,
        "constraints": {
            "merchant_floor_enforced": True,
            "merchant_floor_amount": merchant_floor
        }
    }
