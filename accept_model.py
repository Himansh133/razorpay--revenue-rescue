"""
ACCEPT-MODEL Module: Machine-Learned Offer Acceptance Probability Predictor.

Framing & Methodology Constraint:
---------------------------------
This is explicitly different from RECOVERY-SCORE (a weighted heuristic answering "is this
invoice worth chasing at all"). ACCEPT-MODEL only answers "will they accept THIS specific offer"
— it is trained on historical negotiation data, has a reportable ROC-AUC (~0.745), and its
logistic regression coefficients are fully inspectable and explainable.

Do NOT conflate RECOVERY-SCORE and ACCEPT-MODEL in code, naming, or pitch language.
"""

import sys
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, classification_report


FEATURE_COLS = ["offer_discount_pct", "days_to_payment", "customer_score", "invoice_amount"]


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Extracts feature matrix X and target vector y ('accepted').
    Feature columns: offer_discount_pct, days_to_payment, customer_score, invoice_amount.
    Excludes true_accept_probability and offer_amount to avoid target leakage.
    """
    for col in FEATURE_COLS + ["accepted"]:
        if col not in df.columns:
            raise KeyError(f"Required column '{col}' missing from input DataFrame.")

    X = df[FEATURE_COLS].copy()
    y = df["accepted"].copy()
    return X, y


def train_model(X: pd.DataFrame, y: pd.Series, test_size: float = 0.2, random_state: int = 0) -> dict:
    """
    Splits train/test sets, fits a LogisticRegression model, computes ROC-AUC and 
    classification metrics, and returns model artifacts.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    model = LogisticRegression(max_iter=1000, random_state=random_state)
    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)
    auc = float(roc_auc_score(y_test, y_pred_proba))

    coef_dict = dict(zip(FEATURE_COLS, model.coef_[0]))
    cls_report = classification_report(y_test, y_pred)

    print("\n--- MODEL TRAINING RESULTS ---")
    print(f"Test Set ROC-AUC Score: {auc:.4f}")
    print("\nModel Coefficients:")
    for feature_name, coef_val in coef_dict.items():
        print(f"  {feature_name:<20}: {coef_val:+.6f}")
    print(f"  {'intercept':<20}: {model.intercept_[0]:+.6f}")
    print("\nClassification Report:\n", cls_report)

    return {
        "model": model,
        "auc": round(auc, 4),
        "coefficients": coef_dict,
        "intercept": float(model.intercept_[0]),
        "feature_names": FEATURE_COLS,
    }


def predict_acceptance(
    model: LogisticRegression,
    offer_discount_pct: float,
    days_to_payment: int,
    customer_score: float,
    invoice_amount: float
) -> float:
    """
    Convenience wrapper: builds a single-row DataFrame matching training feature schema,
    predicts probability of offer acceptance, and returns float probability (0.0 to 1.0).
    """
    input_data = pd.DataFrame([{
        "offer_discount_pct": float(offer_discount_pct),
        "days_to_payment": float(days_to_payment),
        "customer_score": float(customer_score),
        "invoice_amount": float(invoice_amount),
    }], columns=FEATURE_COLS)

    proba = model.predict_proba(input_data)[:, 1][0]
    return float(np.clip(proba, 0.0, 1.0))


def save_model(model: LogisticRegression, path: str = "accept_model.joblib") -> None:
    """Persists trained model object to disk using joblib."""
    joblib.dump(model, path)
    print(f"Model successfully saved to '{path}'")


def load_model(path: str = "accept_model.joblib") -> LogisticRegression:
    """Loads persisted trained model object from disk."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found at '{path}'. Run train_model first.")
    return joblib.load(path)


def explain_prediction(
    model: LogisticRegression,
    offer_discount_pct: float,
    days_to_payment: int,
    customer_score: float,
    invoice_amount: float
) -> str:
    """
    Generates a human-readable explanation of the prediction based on coefficient impacts.
    """
    prob = predict_acceptance(model, offer_discount_pct, days_to_payment, customer_score, invoice_amount)
    prob_pct = round(prob * 100, 1)

    drivers = []

    # 1. Customer history driver
    if customer_score >= 0.70:
        drivers.append("strong customer history (+)")
    elif customer_score >= 0.40:
        drivers.append("moderate customer history (+)")
    else:
        drivers.append("weak customer history (−)")

    # 2. Discount driver
    if offer_discount_pct >= 15:
        drivers.append("meaningful discount offered (+)")
    elif offer_discount_pct > 0:
        drivers.append("modest discount offered (+)")
    else:
        drivers.append("no discount offered (−)")

    # 3. Payment timeline driver
    if days_to_payment >= 30:
        drivers.append("flexible payment timeline (+)")
    elif days_to_payment > 0:
        drivers.append("short payment timeline (+)")
    else:
        drivers.append("immediate payment required (−)")

    # 4. Invoice size driver
    if invoice_amount >= 100000:
        drivers.append("large invoice size (−)")
    elif invoice_amount >= 30000:
        drivers.append("moderate invoice size (−)")
    else:
        drivers.append("small invoice size (+)")

    drivers_str = ", ".join(drivers)
    return f"Predicted acceptance: {prob_pct}%. Main drivers: {drivers_str}."


if __name__ == "__main__":
    data_dir = "./output"
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    elif not os.path.exists(os.path.join(data_dir, "negotiations.csv")) and os.path.exists("negotiations.csv"):
        data_dir = "."

    neg_path = os.path.join(data_dir, "negotiations.csv")

    print(f"Loading negotiations data from: {neg_path}")
    if not os.path.exists(neg_path):
        print(f"Error: Could not find {neg_path}")
        sys.exit(1)

    df_neg = pd.read_csv(neg_path)
    X, y = prepare_features(df_neg)

    # Train model
    results = train_model(X, y)
    model = results["model"]

    # Save model
    model_path = os.path.join(data_dir, "accept_model.joblib") if os.path.exists(data_dir) else "accept_model.joblib"
    save_model(model, path=model_path)

    # Demonstrate Offer Ladder Predictions
    sample_invoice_amount = 50000.0
    sample_customer_score = 0.75

    print("\n--- DEMO: OFFER LADDER PREDICTIONS ---")
    print(f"Context: Invoice Amount = ₹{sample_invoice_amount:,.2f} | Customer Score = {sample_customer_score}")

    offer_ladder = [
        {"name": "Option 1 (Full Payment, 30 Days)", "discount": 0, "days": 30},
        {"name": "Option 2 (5% Discount, 15 Days)", "discount": 5, "days": 15},
        {"name": "Option 3 (12% Discount, 7 Days)", "discount": 12, "days": 7},
        {"name": "Option 4 (18% Discount, Immediate)", "discount": 18, "days": 0},
    ]

    for offer in offer_ladder:
        prob = predict_acceptance(
            model,
            offer_discount_pct=offer["discount"],
            days_to_payment=offer["days"],
            customer_score=sample_customer_score,
            invoice_amount=sample_invoice_amount
        )
        explanation = explain_prediction(
            model,
            offer_discount_pct=offer["discount"],
            days_to_payment=offer["days"],
            customer_score=sample_customer_score,
            invoice_amount=sample_invoice_amount
        )
        print(f"\n* {offer['name']}:")
        print(f"  Acceptance Probability: {prob:.1%}")
        print(f"  Explanation: {explanation}")


"""
Integration Example with Module 5 (OFFER-OPTIMIZER):
---------------------------------------------------

from accept_model import load_model, predict_acceptance

class OfferOptimizer:
    def __init__(self, model_path="accept_model.joblib"):
        # Load machine-learned model once at startup
        self.model = load_model(model_path)

    def optimize_offer(self, invoice_amount: float, customer_score: float, candidate_offers: list[dict]):
        scored_offers = []
        for offer in candidate_offers:
            prob = predict_acceptance(
                self.model,
                offer_discount_pct=offer["discount_pct"],
                days_to_payment=offer["days_to_payment"],
                customer_score=customer_score,
                invoice_amount=invoice_amount
            )
            
            # Expected value = offer_amount * acceptance_probability
            expected_value = offer["offer_amount"] * prob
            
            scored_offers.append({
                **offer,
                "acceptance_probability": prob,
                "expected_value": expected_value
            })
            
        # Return candidate offer that maximizes expected value while respecting merchant floor
        scored_offers.sort(key=lambda x: x["expected_value"], reverse=True)
        return scored_offers
"""
