"""
Seed Demo Customer & Invoice Script

Usage:
1. Local Development (SQLite):
   PYTHONPATH=. python scripts/seed_demo_customer.py

2. Production (PostgreSQL):
   DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname" \
   PYTHONPATH=. python scripts/seed_demo_customer.py
"""

import os
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
from backend.config import DATA_DIR
from backend.db.database import init_db, SessionLocal
from backend.db.models import InvoiceModel

DEMO_CUSTOMER_ID = os.getenv("DEMO_CUSTOMER_ID", "CUST_DEMO_001")
DEMO_INVOICE_ID = os.getenv("DEMO_INVOICE_ID", "INV_DEMO_001")


def format_phone(phone_raw: str) -> str:
    phone = (phone_raw or "").strip()
    if phone and not phone.startswith("+"):
        if len(phone) == 10:
            return f"+91{phone}"
        elif len(phone) == 12 and phone.startswith("91"):
            return f"+{phone}"
        else:
            return f"+{phone}"
    return phone or "+919876543210"


def seed_single_demo_record(
    customer_id: str,
    invoice_id: str,
    name: str,
    email: str,
    phone: str,
    amount: float,
    status: str = "overdue",
    days_overdue: int = 30
) -> Dict[str, Any]:
    phone = format_phone(phone)
    init_db()
    db = SessionLocal()
    try:
        inv = db.query(InvoiceModel).filter(InvoiceModel.invoice_id == invoice_id).first()
        if inv:
            inv.customer_id = customer_id
            inv.amount = amount
            inv.status = status
            inv.recovered_amount = 0.0
        else:
            new_inv = InvoiceModel(
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                status=status,
                recovered_amount=0.0
            )
            db.add(new_inv)
        db.commit()
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Database error seeding demo invoice {invoice_id}: {e}")
    finally:
        db.close()

    cust_path = Path(DATA_DIR) / "customers.csv"
    inv_path = Path(DATA_DIR) / "invoices.csv"

    if cust_path.exists():
        cust_df = pd.read_csv(cust_path)
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
                "ltv": amount * 2 if amount > 0 else 1000.0,
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

    if inv_path.exists():
        inv_df = pd.read_csv(inv_path)
        inv_mask = inv_df["invoice_id"] == invoice_id
        if inv_mask.any():
            inv_df.loc[inv_mask, "customer_id"] = customer_id
            inv_df.loc[inv_mask, "amount"] = amount
            inv_df.loc[inv_mask, "status"] = status
            inv_df.loc[inv_mask, "days_overdue"] = days_overdue
        else:
            new_invoice = {
                "invoice_id": invoice_id,
                "customer_id": customer_id,
                "amount": amount,
                "issue_date": "2026-07-01",
                "due_date": "2026-08-01",
                "days_overdue": days_overdue,
                "status": status
            }
            inv_df = pd.concat([inv_df, pd.DataFrame([new_invoice])], ignore_index=True)
        inv_df.to_csv(inv_path, index=False)

    return {
        "customer_id": customer_id,
        "name": name,
        "email": email,
        "phone": phone,
        "invoice_id": invoice_id,
        "amount": amount,
        "status": status
    }


def seed_demo_customer() -> List[Dict[str, Any]]:
    # 1. Demo Customer 1 (Himanshu Demo / Default Demo)
    d1 = seed_single_demo_record(
        customer_id=os.getenv("DEMO_CUSTOMER_ID", "CUST_DEMO_001"),
        invoice_id=os.getenv("DEMO_INVOICE_ID", "INV_DEMO_001"),
        name=os.getenv("DEMO_CUSTOMER_NAME", "Himanshu Demo"),
        email=os.getenv("DEMO_CUSTOMER_EMAIL", "himanshu2967@gmail.com"),
        phone=os.getenv("DEMO_CUSTOMER_PHONE", "+919110058109"),
        amount=float(os.getenv("DEMO_INVOICE_AMOUNT", "50000.0"))
    )

    # 2. Demo Customer 2 (For Live ₹10 Razorpay Testing)
    d2 = seed_single_demo_record(
        customer_id=os.getenv("DEMO_CUSTOMER_ID_2", "CUST_DEMO_002"),
        invoice_id=os.getenv("DEMO_INVOICE_ID_2", "INV_DEMO_002"),
        name=os.getenv("DEMO_CUSTOMER_NAME_2", "Shreyanshu Kumar"),
        email=os.getenv("DEMO_CUSTOMER_EMAIL_2", "niruramesh501@gmail.com"),
        phone=os.getenv("DEMO_CUSTOMER_PHONE_2", "+919110058109"),
        amount=float(os.getenv("DEMO_INVOICE_AMOUNT_2", "10.0"))
    )

    print("==================================================")
    print("✅ DEMO CUSTOMERS & INVOICES SEEDED SUCCESSFULLY")
    print("==================================================")
    for res in [d1, d2]:
        print(f"Customer ID    : {res['customer_id']}")
        print(f"Customer Name  : {res['name']}")
        print(f"Customer Email : {res['email']}")
        print(f"Customer Phone : {res['phone']}")
        print(f"Invoice ID     : {res['invoice_id']}")
        print(f"Invoice Amount : ₹{res['amount']:,.2f}")
        print(f"Status         : {res['status']}")
        print("--------------------------------------------------")

    return [d1, d2]


if __name__ == "__main__":
    seed_demo_customer()
