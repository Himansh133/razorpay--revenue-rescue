"""
Seed Demo Customer & Invoice Script

Usage:
1. Local Development (SQLite):
   DEMO_CUSTOMER_NAME="Aarav Sharma" \
   DEMO_CUSTOMER_EMAIL="aarav.sharma@example.com" \
   DEMO_CUSTOMER_PHONE="+919876543210" \
   DEMO_INVOICE_AMOUNT=50000.0 \
   PYTHONPATH=. python scripts/seed_demo_customer.py

2. Production (PostgreSQL):
   DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname" \
   DEMO_CUSTOMER_NAME="Aarav Sharma" \
   DEMO_CUSTOMER_EMAIL="aarav.sharma@example.com" \
   DEMO_CUSTOMER_PHONE="+919876543210" \
   DEMO_INVOICE_AMOUNT=50000.0 \
   PYTHONPATH=. python scripts/seed_demo_customer.py
"""

import os
from pathlib import Path
import pandas as pd
from backend.config import DATA_DIR
from backend.db.database import init_db, SessionLocal
from backend.db.models import InvoiceModel

DEMO_CUSTOMER_ID = os.getenv("DEMO_CUSTOMER_ID", "CUST_DEMO_001")
DEMO_INVOICE_ID = os.getenv("DEMO_INVOICE_ID", "INV_DEMO_001")


def seed_demo_customer():
    # 1. Read customer & invoice details strictly from environment variables (with default fallbacks)
    name = os.getenv("DEMO_CUSTOMER_NAME", "Demo Customer")
    email = os.getenv("DEMO_CUSTOMER_EMAIL", "demo.customer@example.com")
    phone = os.getenv("DEMO_CUSTOMER_PHONE", "+919876543210").strip()
    if phone and not phone.startswith("+"):
        if len(phone) == 10:
            phone = f"+91{phone}"
        elif len(phone) == 12 and phone.startswith("91"):
            phone = f"+{phone}"
        else:
            phone = f"+{phone}"
    
    raw_amount = os.getenv("DEMO_INVOICE_AMOUNT", "50000.0")
    try:
        amount = float(raw_amount)
    except (ValueError, TypeError):
        amount = 50000.0

    customer_id = DEMO_CUSTOMER_ID
    invoice_id = DEMO_INVOICE_ID

    # 2. Upsert Invoice in Database via SQLAlchemy (Works for both SQLite & PostgreSQL)
    init_db()
    db = SessionLocal()
    db_created_or_updated = False
    try:
        inv = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == invoice_id).first()
        if inv:
            inv.customer_id = customer_id
            inv.amount = amount
            inv.status = "overdue"
            inv.recovered_amount = 0.0
            db_created_or_updated = True
        else:
            new_inv = InvoiceModel(
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                status="overdue",
                recovered_amount=0.0
            )
            db.add(new_inv)
            db_created_or_updated = True
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Database error seeding demo invoice: {e}")
    finally:
        db.close()

    # 3. Upsert Customer & Invoice in CSV Datasets for in-memory API resolution
    cust_path = Path(DATA_DIR) / "customers.csv"
    inv_path = Path(DATA_DIR) / "invoices.csv"

    # Seed customers.csv
    if cust_path.exists():
        cust_df = pd.read_csv(cust_path)
        # Ensure email and phone columns exist with object dtype
        if "email" not in cust_df.columns:
            cust_df["email"] = ""
        if "phone" not in cust_df.columns:
            cust_df["phone"] = ""
        
        cust_df["email"] = cust_df["email"].astype(str)
        cust_df["phone"] = cust_df["phone"].astype(str)

        cust_mask = cust_df["customer_id"] == customer_id
        if cust_mask.any():
            cust_df.loc[cust_mask, "name"] = name
            cust_df.loc[cust_mask, "email"] = email
            cust_df.loc[cust_mask, "phone"] = phone
            cust_df.loc[cust_mask, "segment"] = "high_value"
        else:
            new_cust = {
                "customer_id": customer_id,
                "name": name,
                "company": "Demo Enterprise",
                "segment": "high_value",
                "ltv": amount * 2,
                "orders": 12,
                "successful_payments": 10,
                "failed_payments": 2,
                "avg_delay_days": 15.0,
                "promises_made": 1,
                "promises_kept": 1,
                "city": "Mumbai",
                "preferred_device": "Desktop",
                "email": email,
                "phone": phone
            }
            cust_df = pd.concat([cust_df, pd.DataFrame([new_cust])], ignore_index=True)
        cust_df.to_csv(cust_path, index=False)

    # Seed invoices.csv
    if inv_path.exists():
        inv_df = pd.read_csv(inv_path)
        inv_mask = inv_df["invoice_id"] == invoice_id
        if inv_mask.any():
            inv_df.loc[inv_mask, "customer_id"] = customer_id
            inv_df.loc[inv_mask, "amount"] = amount
            inv_df.loc[inv_mask, "status"] = "overdue"
            inv_df.loc[inv_mask, "days_overdue"] = 30
        else:
            new_invoice = {
                "invoice_id": invoice_id,
                "customer_id": customer_id,
                "amount": amount,
                "issue_date": "2026-07-01",
                "due_date": "2026-08-01",
                "days_overdue": 30,
                "status": "overdue"
            }
            inv_df = pd.concat([inv_df, pd.DataFrame([new_invoice])], ignore_index=True)
        inv_df.to_csv(inv_path, index=False)

    # 4. Safe Printing (No secrets/keys/database URLs)
    print("==================================================")
    print("✅ DEMO CUSTOMER & INVOICE SEEDED SUCCESSFULLY")
    print("==================================================")
    print(f"Customer ID    : {customer_id}")
    print(f"Customer Name  : {name}")
    print(f"Customer Email : {email}")
    print(f"Customer Phone : {phone}")
    print(f"Invoice ID     : {invoice_id}")
    print(f"Invoice Amount : ₹{amount:,.2f}")
    print(f"Status         : overdue")
    print("==================================================")

    return {
        "customer_id": customer_id,
        "name": name,
        "email": email,
        "phone": phone,
        "invoice_id": invoice_id,
        "amount": amount
    }


if __name__ == "__main__":
    seed_demo_customer()
