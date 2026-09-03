import os
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from backend.config import DATA_DIR, BASE_DIR

MODEL_PATH = Path(BASE_DIR) / "ml" / "model.pkl"
FEATURE_COLS = ["offer_discount_pct", "days_to_payment", "customer_score", "invoice_amount"]

def prepare_features(df: pd.DataFrame):
    for col in FEATURE_COLS + ["accepted"]:
        if col not in df.columns:
            raise KeyError(f"Required column '{col}' missing from input DataFrame.")
    X = df[FEATURE_COLS].copy()
    y = df["accepted"].copy()
    return X, y

def train_and_save():
    neg_path = Path(DATA_DIR) / "negotiations.csv"
    if not neg_path.exists():
        raise FileNotFoundError(f"negotiations.csv not found at {neg_path}")

    df_neg = pd.read_csv(neg_path)
    X, y = prepare_features(df_neg)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, y_pred_proba))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"ACCEPT-MODEL trained successfully & saved to {MODEL_PATH}. ROC-AUC: {auc:.4f}")
    return model

def load_model():
    if not MODEL_PATH.exists():
        return train_and_save()
    return joblib.load(MODEL_PATH)

def predict_acceptance(features_dict: dict) -> float:
    model = load_model()
    input_data = pd.DataFrame([{
        "offer_discount_pct": float(features_dict.get("discount_pct", 10.0)),
        "days_to_payment": float(features_dict.get("days_to_payment", 30)),
        "customer_score": float(features_dict.get("customer_score", 0.75)),
        "invoice_amount": float(features_dict.get("invoice_amount", 100000.0)),
    }], columns=FEATURE_COLS)

    proba = model.predict_proba(input_data)[:, 1][0]
    return float(np.clip(proba, 0.0, 1.0))

if __name__ == "__main__":
    train_and_save()
