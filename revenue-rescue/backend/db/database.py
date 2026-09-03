import sqlite3
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any
from backend.config import DB_PATH
from backend.db.models import AuditEvent

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

def get_connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            detail TEXT NOT NULL,
            summary TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_id ON audit_events (invoice_id)")
    conn.commit()
    conn.close()

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

    conn = get_connection()
    cursor = conn.cursor()
    
    # Idempotency check for identical minute log
    minute_prefix = timestamp_iso[:16]
    cursor.execute("""
        SELECT event_id, timestamp FROM audit_events 
        WHERE invoice_id = ? AND event_type = ? AND timestamp LIKE ?
    """, (invoice_id, event_type, f"{minute_prefix}%"))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return get_event_by_id(existing["event_id"])

    cursor.execute("""
        INSERT INTO audit_events (event_id, invoice_id, timestamp, event_type, actor, detail, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_id, invoice_id, timestamp_iso, event_type, actor, json.dumps(detail), summary_str))

    conn.commit()
    conn.close()

    return AuditEvent(
        event_id=event_id,
        invoice_id=invoice_id,
        timestamp=timestamp_iso,
        event_type=event_type,
        actor=actor,
        detail=detail,
        summary=summary_str
    )

def get_event_by_id(event_id: str) -> AuditEvent:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ValueError(f"Event {event_id} not found")
    return AuditEvent(
        event_id=row["event_id"],
        invoice_id=row["invoice_id"],
        timestamp=row["timestamp"],
        event_type=row["event_type"],
        actor=row["actor"],
        detail=json.loads(row["detail"]),
        summary=row["summary"]
    )

def get_trail(invoice_id: str) -> List[AuditEvent]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_events WHERE invoice_id = ? ORDER BY timestamp ASC", (invoice_id,))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        events.append(AuditEvent(
            event_id=r["event_id"],
            invoice_id=r["invoice_id"],
            timestamp=r["timestamp"],
            event_type=r["event_type"],
            actor=r["actor"],
            detail=json.loads(r["detail"]),
            summary=r["summary"]
        ))
    return events

def get_trail_summary(invoice_id: str) -> str:
    events = get_trail(invoice_id)
    if not events:
        return f"No audit events found for invoice {invoice_id}"

    lines = []
    for evt in events:
        hhmm = evt.timestamp[11:16] if len(evt.timestamp) >= 16 else "00:00"
        lines.append(f"{hhmm}  {evt.summary}")
    return "\n".join(lines)
