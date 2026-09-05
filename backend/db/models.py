import uuid
import datetime
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class InvoiceModel(Base):
    __tablename__ = "invoices"

    invoice_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="overdue", nullable=False)
    recovered_amount = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    payments = relationship("PaymentModel", back_populates="invoice")
    outreach_records = relationship("OutreachRecordModel", back_populates="invoice")

class PaymentModel(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: f"pay_{uuid.uuid4().hex[:12]}")
    invoice_id = Column(String, ForeignKey("invoices.invoice_id"), index=True, nullable=False)
    razorpay_payment_id = Column(String, unique=True, index=True, nullable=True)
    razorpay_order_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="captured", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    invoice = relationship("InvoiceModel", back_populates="payments")

class WebhookEventModel(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=lambda: f"whevt_{uuid.uuid4().hex[:12]}")
    razorpay_event_id = Column(String, unique=True, index=True, nullable=True)
    event_type = Column(String, nullable=False)
    razorpay_payment_id = Column(String, nullable=True)
    payload = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="processed")

class AuditEventModel(Base):
    __tablename__ = "audit_events"

    event_id = Column(String, primary_key=True, default=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    invoice_id = Column(String, index=True, nullable=False)
    timestamp = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    actor = Column(String, default="system", nullable=False)
    detail = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)

class OutreachRecordModel(Base):
    __tablename__ = "outreach_records"

    id = Column(String, primary_key=True, default=lambda: f"outr_{uuid.uuid4().hex[:12]}")
    invoice_id = Column(String, ForeignKey("invoices.invoice_id"), index=True, nullable=False)
    customer_id = Column(String, index=True, nullable=False)
    channel = Column(String, nullable=False)  # "email" or "sms"
    recipient = Column(String, nullable=False)
    status = Column(String, nullable=False)   # "sent", "failed", "already_sent", "unavailable"
    provider = Column(String, nullable=False) # "resend", "twilio", "mock"
    provider_message_id = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

    invoice = relationship("InvoiceModel", back_populates="outreach_records")
