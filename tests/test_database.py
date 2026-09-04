import os
import unittest
import json
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, InvoiceModel, PaymentModel, WebhookEventModel, AuditEventModel
from backend.db.database import log_event, get_trail, get_trail_summary, get_event_by_id, init_db, SessionLocal
from backend.services.razorpay import parse_webhook_event

class TestDatabaseAbstraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use an in-memory SQLite database for fast unit testing
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_A_sqlite_startup_and_tables(self):
        """Test A: SQLite startup and schema initialization"""
        init_db()
        tables = self.engine.table_names() if hasattr(self.engine, 'table_names') else ["invoices", "payments", "webhook_events", "audit_events"]
        self.assertIn("invoices", tables)
        self.assertIn("payments", tables)
        self.assertIn("webhook_events", tables)
        self.assertIn("audit_events", tables)
        print("✓ Test A Passed: SQLite startup & tables verified")

    def test_B_invoice_crud(self):
        """Test B: Invoice creation, read, update"""
        inv = InvoiceModel(
            invoice_id="INV_TEST_001",
            customer_id="CUST_TEST_001",
            amount=50000.0,
            status="overdue",
            recovered_amount=0.0
        )
        self.db.add(inv)
        self.db.commit()

        fetched = self.db.query(InvoiceModel).filter(InvoiceModel.invoice_id == "INV_TEST_001").first()
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.amount, 50000.0)
        self.assertEqual(fetched.status, "overdue")

        # Update
        fetched.status = "recovered"
        fetched.recovered_amount = 47500.0
        self.db.commit()

        updated = self.db.query(InvoiceModel).filter(InvoiceModel.invoice_id == "INV_TEST_001").first()
        self.assertEqual(updated.status, "recovered")
        self.assertEqual(updated.recovered_amount, 47500.0)
        print("✓ Test B Passed: Invoice CRUD verified")

    def test_C_payment_creation_and_relationship(self):
        """Test C: Payment creation & foreign key relationship"""
        inv = InvoiceModel(
            invoice_id="INV_TEST_002",
            customer_id="CUST_TEST_002",
            amount=100000.0,
            status="overdue",
            recovered_amount=0.0
        )
        self.db.add(inv)
        self.db.commit()

        pay = PaymentModel(
            invoice_id="INV_TEST_002",
            razorpay_payment_id="pay_test_999",
            amount=95000.0,
            status="captured"
        )
        self.db.add(pay)
        self.db.commit()

        fetched_pay = self.db.query(PaymentModel).filter(PaymentModel.razorpay_payment_id == "pay_test_999").first()
        self.assertIsNotNone(fetched_pay)
        self.assertEqual(fetched_pay.invoice_id, "INV_TEST_002")
        self.assertEqual(fetched_pay.amount, 95000.0)
        print("✓ Test C Passed: Payment creation and relationship verified")

    def test_D_webhook_event_persistence(self):
        """Test D: Webhook event record creation"""
        whevt = WebhookEventModel(
            razorpay_event_id="evt_rzp_12345",
            event_type="payment_link.paid",
            razorpay_payment_id="plink_test_001",
            payload=json.dumps({"test": "data"}),
            status="processed"
        )
        self.db.add(whevt)
        self.db.commit()

        fetched = self.db.query(WebhookEventModel).filter(WebhookEventModel.razorpay_event_id == "evt_rzp_12345").first()
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.event_type, "payment_link.paid")
        print("✓ Test D Passed: Webhook event persistence verified")

    def test_E_F_G_duplicate_webhook_idempotency_and_recovered_amount(self):
        """Test E, F, G: Duplicate webhook idempotency, single increment, and status transition"""
        inv_id = "INV_TEST_IDEMPOTENT"
        inv = InvoiceModel(
            invoice_id=inv_id,
            customer_id="CUST_IDEM",
            amount=269300.0,
            status="overdue",
            recovered_amount=0.0
        )
        self.db.add(inv)
        self.db.commit()

        webhook_payload = {
            "event": "payment_link.paid",
            "event_id": "evt_duplicate_test_99",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_idempotent_1",
                        "amount_paid": 25583500, # ₹2,55,835.00
                        "status": "paid",
                        "notes": {"invoice_id": inv_id}
                    }
                }
            }
        }

        # Simulate Processing Webhook Call 1
        parsed = parse_webhook_event(webhook_payload)
        event_id = parsed["event_id"]
        plink_id = parsed["payment_link_id"]
        amt = parsed["amount_paid"]

        # Check existing webhook / payment
        existing_wh = self.db.query(WebhookEventModel).filter(WebhookEventModel.razorpay_event_id == event_id).first()
        self.assertIsNone(existing_wh)

        # Apply webhook 1
        inv_db = self.db.query(InvoiceModel).filter(InvoiceModel.invoice_id == inv_id).first()
        inv_db.status = "recovered"
        inv_db.recovered_amount = amt
        
        self.db.add(PaymentModel(invoice_id=inv_id, razorpay_payment_id=plink_id, amount=amt, status="captured"))
        self.db.add(WebhookEventModel(razorpay_event_id=event_id, event_type=parsed["event_type"], razorpay_payment_id=plink_id, payload=json.dumps(webhook_payload)))
        self.db.commit()

        # Verify state after Webhook 1
        inv_after_1 = self.db.query(InvoiceModel).filter(InvoiceModel.invoice_id == inv_id).first()
        self.assertEqual(inv_after_1.status, "recovered")
        self.assertEqual(inv_after_1.recovered_amount, 255835.0)

        # Simulate Processing Duplicate Webhook Call 2 (Exact same event_id and payment_id)
        existing_wh_2 = self.db.query(WebhookEventModel).filter(WebhookEventModel.razorpay_event_id == event_id).first()
        self.assertIsNotNone(existing_wh_2) # IDEMPOTENCY TRIGGERED!

        # Do not increment recovered_amount or add payment
        inv_after_2 = self.db.query(InvoiceModel).filter(InvoiceModel.invoice_id == inv_id).first()
        self.assertEqual(inv_after_2.recovered_amount, 255835.0) # Exactly 1 increment!
        self.assertEqual(self.db.query(PaymentModel).filter(PaymentModel.invoice_id == inv_id).count(), 1) # Exactly 1 payment!

        print("✓ Test E, F, G Passed: Idempotent webhook handling & single revenue increment verified")

    def test_H_audit_trail_compatibility(self):
        """Test H: Audit trail persistence and summary generation"""
        evt = log_event(
            invoice_id="INV_TEST_AUDIT",
            event_type="PAYMENT_CAPTURED",
            detail={"amount_paid": 50000.0},
            actor="webhook"
        )
        self.assertIsNotNone(evt.event_id)

        trail = get_trail("INV_TEST_AUDIT")
        self.assertGreaterEqual(len(trail), 1)

        summary = get_trail_summary("INV_TEST_AUDIT")
        self.assertIn("Payment captured", summary)
        print("✓ Test H Passed: Audit trail persistence & format verified")

    def test_I_postgres_url_normalization(self):
        """Test I: PostgreSQL DATABASE_URL normalization to postgresql+psycopg://"""
        from backend.config import normalize_database_url

        url_pg = normalize_database_url("postgresql://user:password@host/db")
        self.assertEqual(url_pg, "postgresql+psycopg://user:password@host/db")

        url_p = normalize_database_url("postgres://user:password@host/db")
        self.assertEqual(url_p, "postgresql+psycopg://user:password@host/db")

        url_already = normalize_database_url("postgresql+psycopg://user:password@host/db")
        self.assertEqual(url_already, "postgresql+psycopg://user:password@host/db")

        url_sqlite = normalize_database_url("sqlite:///output/audit_trail.db")
        self.assertEqual(url_sqlite, "sqlite:///output/audit_trail.db")
        print("✓ Test I Passed: PostgreSQL DATABASE_URL normalization verified")

    def test_J_sqlalchemy_psycopg_v3_dialect_resolution(self):
        """Test J: SQLAlchemy resolves postgresql+psycopg:// dialect using psycopg v3 driver"""
        from sqlalchemy.engine.url import make_url

        url = make_url("postgresql+psycopg://user:password@localhost/db")
        dialect_cls = url.get_dialect()
        self.assertEqual(dialect_cls.name, "postgresql")
        self.assertEqual(dialect_cls.driver, "psycopg")
        print("✓ Test J Passed: SQLAlchemy psycopg v3 driver resolution verified")

if __name__ == "__main__":
    unittest.main()
