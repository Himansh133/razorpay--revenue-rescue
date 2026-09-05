import os
import pytest
import pandas as pd
from backend.config import DATA_DIR
from backend.db.database import SessionLocal, init_db
from backend.db.models import InvoiceModel
from scripts.seed_demo_customer import seed_demo_customer, DEMO_CUSTOMER_ID, DEMO_INVOICE_ID


def test_seed_demo_customer_idempotency(monkeypatch):
    """
    Verifies that running seed_demo_customer() creates the record on first run
    and updates it idempotently on subsequent runs without creating duplicate DB or CSV records.
    """
    # Configure custom test env vars
    monkeypatch.setenv("DEMO_CUSTOMER_NAME", "Test Seed Customer")
    monkeypatch.setenv("DEMO_CUSTOMER_EMAIL", "test.seed@example.com")
    monkeypatch.setenv("DEMO_CUSTOMER_PHONE", "+919998887776")
    monkeypatch.setenv("DEMO_INVOICE_AMOUNT", "75000.0")

    # First Run
    res1 = seed_demo_customer()
    assert res1["customer_id"] == DEMO_CUSTOMER_ID
    assert res1["invoice_id"] == DEMO_INVOICE_ID
    assert res1["amount"] == 75000.0

    # Query DB to check count of invoices with DEMO_INVOICE_ID
    init_db()
    db = SessionLocal()
    try:
        inv_count_1 = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == DEMO_INVOICE_ID).count()
        assert inv_count_1 == 1, "Database should contain exactly 1 demo invoice after first seed run"
    finally:
        db.close()

    # Query CSV files to check count
    cust_df1 = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
    inv_df1 = pd.read_csv(os.path.join(DATA_DIR, "invoices.csv"))
    
    cust_matches_1 = cust_df1[cust_df1["customer_id"] == DEMO_CUSTOMER_ID]
    inv_matches_1 = inv_df1[inv_df1["invoice_id"] == DEMO_INVOICE_ID]
    assert len(cust_matches_1) == 1, "customers.csv should contain exactly 1 demo customer after first seed run"
    assert len(inv_matches_1) == 1, "invoices.csv should contain exactly 1 demo invoice after first seed run"

    # Second Run (Idempotency check with updated amount)
    monkeypatch.setenv("DEMO_INVOICE_AMOUNT", "80000.0")
    res2 = seed_demo_customer()
    assert res2["amount"] == 80000.0

    # Verify DB count is STILL exactly 1 (no duplicates)
    db = SessionLocal()
    try:
        inv_rows = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == DEMO_INVOICE_ID).all()
        assert len(inv_rows) == 1, "Database should still contain exactly 1 demo invoice after second seed run"
        assert inv_rows[0].amount == 80000.0, "Invoice amount should be updated idempotently in DB"
    finally:
        db.close()

    # Verify CSV count is STILL exactly 1 (no duplicates)
    cust_df2 = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
    inv_df2 = pd.read_csv(os.path.join(DATA_DIR, "invoices.csv"))

    cust_matches_2 = cust_df2[cust_df2["customer_id"] == DEMO_CUSTOMER_ID]
    inv_matches_2 = inv_df2[inv_df2["invoice_id"] == DEMO_INVOICE_ID]
    assert len(cust_matches_2) == 1, "customers.csv should still contain exactly 1 demo customer (no duplicates)"
    assert len(inv_matches_2) == 1, "invoices.csv should still contain exactly 1 demo invoice (no duplicates)"
    assert inv_matches_2.iloc[0]["amount"] == 80000.0, "Invoice amount in CSV should be updated idempotently"
