import json
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from backend.config import DATABASE_URL, DB_PATH
from backend.db.models import Base, InvoiceModel, PaymentModel, WebhookEventModel, AuditEventModel
from backend.models.schemas import AuditEvent

VALID_EVENT_TYPES = {
    "LEAK_DETECTED",
    "INVOICE_SCORED",
    "RECOVERY_STARTED",
    "CUSTOMER_ANALYZED",
    "OFFERS_EVALUATED",
    "OFFER_SELECTED",
    "OFFER_REJECTED_BELOW_FLOOR",
    "ESCALATED_TO_HUMAN",
    "PAYMENT_LINK_CREATED",
    "PAYMENT_CAPTURED",
    "PAYMENT_FAILED"
}

engine_kwargs = {}
if "sqlite" in DATABASE_URL.lower():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    if "sqlite" in DATABASE_URL.lower():
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

def build_summary(event_type: str, detail: Dict[str, Any]) -> str:
    if event_type == "LEAK_DETECTED":
        segment = detail.get("segment", "unknown")
        impact = detail.get("impact_rupees", 0.0)
        return f"Revenue leak detected in {segment} (Impact: ₹{impact:,.0f})"
    elif event_type == "INVOICE_SCORED":
        score = detail.get("recovery_score", 0.0)
        tier = detail.get("tier", "unknown")
        return f"Invoice recoverability scored: {score:.2f} (Tier: '{tier}')"
    elif event_type == "RECOVERY_STARTED":
        return "Recovery negotiation process initiated"
    elif event_type == "CUSTOMER_ANALYZED":
        cid = detail.get("customer_id", "")
        ltv = detail.get("ltv", 0.0)
        score = detail.get("score", 0.0)
        return f"Customer {cid} profile analyzed (LTV ₹{ltv:,.0f}, Score {score:.2f})"
    elif event_type == "OFFERS_EVALUATED":
        count = detail.get("candidates_count", 0)
        return f"Evaluated {count} candidate recovery offers"
    elif event_type == "OFFER_SELECTED":
        amt = detail.get("offer_amount", 0.0)
        disc = detail.get("discount_pct", 0.0)
        terms = detail.get("days_to_payment", 0)
        ev = detail.get("expected_value", 0.0)
        return f"Selected ₹{amt:,.0f} offer ({disc:.1f}% discount, {terms}-day terms, EV ₹{ev:,.0f})"
    elif event_type == "OFFER_REJECTED_BELOW_FLOOR":
        amt = detail.get("offer_amount", 0.0)
        disc = detail.get("discount_pct", 0.0)
        floor = detail.get("merchant_floor", 0.0)
        return f"Rejected ₹{amt:,.0f} offer ({disc:.1f}% discount) — below merchant floor ₹{floor:,.0f}"
    elif event_type == "ESCALATED_TO_HUMAN":
        reason = detail.get("reason", "manual review needed")
        return f"Escalated to human operator ({reason})"
    elif event_type == "PAYMENT_LINK_CREATED":
        amt = detail.get("amount", 0.0)
        return f"Razorpay payment link created for ₹{amt:,.0f}"
    elif event_type == "PAYMENT_CAPTURED":
        amt = detail.get("amount_paid", 0.0)
        return f"Payment captured: ₹{amt:,.0f} recovered"
    elif event_type == "PAYMENT_FAILED":
        reason = detail.get("reason", "transaction declined")
        return f"Payment link execution failed ({reason})"
    return f"Event {event_type} logged"

def log_event(invoice_id: str, event_type: str, detail: Dict[str, Any], actor: str = "system") -> AuditEvent:
    init_db()
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Invalid event_type '{event_type}'. Must be one of {VALID_EVENT_TYPES}")

    timestamp_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    summary_str = build_summary(event_type, detail)
    event_id = f"evt_{uuid.uuid4().hex[:12]}"

    db: Session = SessionLocal()
    try:
        minute_prefix = timestamp_iso[:16]
        existing = db.query(AuditEventModel).filter(
            AuditEventModel.invoice_id == invoice_id,
            AuditEventModel.event_type == event_type,
            AuditEventModel.timestamp.like(f"{minute_prefix}%")
        ).first()

        if existing:
            return AuditEvent(
                event_id=existing.event_id,
                invoice_id=existing.invoice_id,
                timestamp=existing.timestamp,
                event_type=existing.event_type,
                actor=existing.actor,
                detail=json.loads(existing.detail),
                summary=existing.summary
            )

        db_event = AuditEventModel(
            event_id=event_id,
            invoice_id=invoice_id,
            timestamp=timestamp_iso,
            event_type=event_type,
            actor=actor,
            detail=json.dumps(detail),
            summary=summary_str
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)

        return AuditEvent(
            event_id=db_event.event_id,
            invoice_id=db_event.invoice_id,
            timestamp=db_event.timestamp,
            event_type=db_event.event_type,
            actor=db_event.actor,
            detail=detail,
            summary=summary_str
        )
    finally:
        db.close()

def get_event_by_id(event_id: str) -> AuditEvent:
    db: Session = SessionLocal()
    try:
        row = db.query(AuditEventModel).filter(AuditEventModel.event_id == event_id).first()
        if not row:
            raise ValueError(f"Event {event_id} not found")
        return AuditEvent(
            event_id=row.event_id,
            invoice_id=row.invoice_id,
            timestamp=row.timestamp,
            event_type=row.event_type,
            actor=row.actor,
            detail=json.loads(row.detail),
            summary=row.summary
        )
    finally:
        db.close()

def get_trail(invoice_id: str) -> List[AuditEvent]:
    init_db()
    db: Session = SessionLocal()
    try:
        rows = db.query(AuditEventModel).filter(AuditEventModel.invoice_id == invoice_id).order_by(AuditEventModel.timestamp.asc()).all()
        events = []
        for r in rows:
            events.append(AuditEvent(
                event_id=r.event_id,
                invoice_id=r.invoice_id,
                timestamp=r.timestamp,
                event_type=r.event_type,
                actor=r.actor,
                detail=json.loads(r.detail),
                summary=r.summary
            ))
        return events
    finally:
        db.close()

def get_trail_summary(invoice_id: str) -> str:
    events = get_trail(invoice_id)
    if not events:
        return f"No audit events found for invoice {invoice_id}"

    lines = []
    for evt in events:
        hhmm = evt.timestamp[11:16] if len(evt.timestamp) >= 16 else "00:00"
        lines.append(f"{hhmm}  {evt.summary}")
    return "\n".join(lines)
