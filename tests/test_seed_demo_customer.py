import os
import pytest
import pandas as pd
from backend.config import DATA_DIR
from backend.db.database import SessionLocal, init_db
from backend.db.models import InvoiceModel
from scripts.seed_demo_customer import seed_demo_customer, DEMO_CUSTOMER_ID, DEMO_INVOICE_ID


def test_seed_demo_customer_idempotency(monkeypatch):
    """
    Verifies that running seed_demo_customer() creates records for CUST_DEMO_001 and CUST_DEMO_002
    and updates them idempotently on subsequent runs without creating duplicate DB or CSV records.
    """
    # Configure custom test env vars
    monkeypatch.setenv("DEMO_CUSTOMER_NAME", "Test Seed Customer")
    monkeypatch.setenv("DEMO_CUSTOMER_EMAIL", "test.seed@example.com")
    monkeypatch.setenv("DEMO_CUSTOMER_PHONE", "+919998887776")
    monkeypatch.setenv("DEMO_INVOICE_AMOUNT", "75000.0")

    # First Run
    records = seed_demo_customer()
    assert len(records) == 2
    res1 = records[0]
    res2 = records[1]
    
    assert res1["customer_id"] == DEMO_CUSTOMER_ID
    assert res1["invoice_id"] == DEMO_INVOICE_ID
    assert res1["amount"] == 75000.0

    assert res2["customer_id"] == "CUST_DEMO_002"
    assert res2["invoice_id"] == "INV_DEMO_002"
    assert res2["amount"] == 10.0
    assert res2["name"] == "Shreyanshu Kumar"
    assert res2["email"] == "niruramesh501@gmail.com"
    assert res2["phone"] == "+919110058109"

    # Query DB to check count of invoices for both demo invoices
    init_db()
    db = SessionLocal()
    try:
        inv_count_1 = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == DEMO_INVOICE_ID).count()
        inv_count_2 = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == "INV_DEMO_002").count()
        assert inv_count_1 == 1, "Database should contain exactly 1 demo invoice 1"
        assert inv_count_2 == 1, "Database should contain exactly 1 demo invoice 2"
    finally:
        db.close()

    # Query CSV files to check count
    cust_df1 = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
    inv_df1 = pd.read_csv(os.path.join(DATA_DIR, "invoices.csv"))
    
    cust_matches_1 = cust_df1[cust_df1["customer_id"] == DEMO_CUSTOMER_ID]
    inv_matches_1 = inv_df1[inv_df1["invoice_id"] == DEMO_INVOICE_ID]
    assert len(cust_matches_1) == 1, "customers.csv should contain exactly 1 demo customer 1"
    assert len(inv_matches_1) == 1, "invoices.csv should contain exactly 1 demo invoice 1"

    cust_matches_2 = cust_df1[cust_df1["customer_id"] == "CUST_DEMO_002"]
    inv_matches_2 = inv_df1[inv_df1["invoice_id"] == "INV_DEMO_002"]
    assert len(cust_matches_2) == 1, "customers.csv should contain exactly 1 demo customer 2"
    assert len(inv_matches_2) == 1, "invoices.csv should contain exactly 1 demo invoice 2"

    # Second Run (Idempotency check)
    records_run2 = seed_demo_customer()
    assert len(records_run2) == 2

    # Verify DB count is STILL exactly 1 for both (no duplicates)
    db = SessionLocal()
    try:
        inv_rows1 = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == DEMO_INVOICE_ID).all()
        inv_rows2 = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == "INV_DEMO_002").all()
        assert len(inv_rows1) == 1, "Database should still contain exactly 1 demo invoice 1"
        assert len(inv_rows2) == 1, "Database should still contain exactly 1 demo invoice 2"
    finally:
        db.close()
