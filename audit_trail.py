"""
AUDIT-TRAIL Module: Timestamped, Append-Only Event Recorder & Compliance Log.

Framing Constraint:
-------------------
This module does not decide anything and does not compute anything. It is a pure recorder.
It writes down what happened in plain, structured form, storing append-only compliance logs
in an SQLite database.
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field

DATA_DIR = "./output" if os.path.exists("./output/invoices.csv") else "."
DB_PATH = os.path.join(DATA_DIR, "audit_trail.db")

# Fixed Event Type Enum Constants
EVENT_TYPES = [
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
    "PAYMENT_FAILED",
]


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    event_type: str
    actor: str = "system"  # "system" | "agent" | "merchant" | "webhook"
    detail: dict[str, Any] = Field(default_factory=dict)
    summary: str


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes SQLite database and creates audit_events table if missing."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_id ON audit_events (invoice_id);")
        conn.commit()


# Initialize DB at module import
init_db()


def _build_summary(event_type: str, invoice_id: str, detail: dict[str, Any]) -> str:
    """Template helper to build a concise human-readable one-line summary."""
    if event_type == "LEAK_DETECTED":
        segment = detail.get("segment", "segment")
        impact = detail.get("impact_rupees", 0.0)
        return f"Revenue leak detected in {segment} (Impact: ₹{impact:,.0f})"
    elif event_type == "INVOICE_SCORED":
        score = detail.get("recovery_score", 0.0)
        tier = detail.get("tier", "standard")
        return f"Invoice recoverability scored: {score:.2f} (Tier: '{tier}')"
    elif event_type == "RECOVERY_STARTED":
        amount = detail.get("amount", 0.0)
        return f"Recovery process initiated for invoice {invoice_id} (₹{amount:,.0f})"
    elif event_type == "CUSTOMER_ANALYZED":
        cust_id = detail.get("customer_id", "")
        ltv = detail.get("ltv", 0.0)
        score = detail.get("customer_score", 0.0)
        return f"Customer {cust_id} profile analyzed (LTV ₹{ltv:,.0f}, Score {score:.2f})"
    elif event_type == "OFFERS_EVALUATED":
        count = detail.get("total_candidates", detail.get("valid_count", 0) + detail.get("rejected_count", 0))
        return f"Evaluated {count} candidate recovery offers"
    elif event_type == "OFFER_SELECTED":
        amt = detail.get("offer_amount", 0.0)
        d_pct = detail.get("discount_pct", 0.0)
        days = detail.get("days_to_payment", 0)
        ev = detail.get("expected_value", 0.0)
        return f"Selected ₹{amt:,.0f} offer ({d_pct}% discount, {days}-day terms, EV ₹{ev:,.0f})"
    elif event_type == "OFFER_REJECTED_BELOW_FLOOR":
        amt = detail.get("offer_amount", 0.0)
        d_pct = detail.get("discount_pct", 0.0)
        floor = detail.get("merchant_floor", 0.0)
        return f"Rejected ₹{amt:,.0f} offer ({d_pct}% discount) — below merchant floor ₹{floor:,.0f}"
    elif event_type == "ESCALATED_TO_HUMAN":
        reason = detail.get("reason", "Escalation requested")
        return f"Escalated to human account manager: {reason}"
    elif event_type == "PAYMENT_LINK_CREATED":
        amt = detail.get("amount", detail.get("offer_amount", 0.0))
        return f"Razorpay payment link created for ₹{amt:,.0f}"
    elif event_type == "PAYMENT_CAPTURED":
        amt = detail.get("amount_paid", detail.get("amount", 0.0))
        return f"Payment captured: ₹{amt:,.0f} recovered"
    elif event_type == "PAYMENT_FAILED":
        return f"Payment failed for invoice {invoice_id}"
    else:
        return f"Event {event_type} logged for invoice {invoice_id}"


def log_event(
    invoice_id: str,
    event_type: str,
    detail: dict[str, Any],
    actor: str = "system",
    db_path: str = DB_PATH
) -> AuditEvent:
    """
    Creates an AuditEvent, auto-generates event_id & timestamp, builds summary template,
    and appends event into the SQLite audit_events table.
    
    Idempotency: Prevents recording duplicate identical events generated in the same second.
    """
    if event_type not in EVENT_TYPES:
        event_type = "RECOVERY_STARTED"  # Fallback to valid type

    summary = _build_summary(event_type, invoice_id, detail)
    event = AuditEvent(
        invoice_id=invoice_id,
        event_type=event_type,
        actor=actor,
        detail=detail,
        summary=summary
    )

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Idempotency check: prevent identical event in the same minute
        cursor.execute("""
            SELECT event_id FROM audit_events 
            WHERE invoice_id = ? AND event_type = ? AND summary = ?
            AND substr(timestamp, 1, 16) = substr(?, 1, 16)
        """, (invoice_id, event_type, summary, event.timestamp))
        existing = cursor.fetchone()
        if existing:
            # Return existing event rather than inserting duplicate
            return AuditEvent(
                event_id=existing[0],
                invoice_id=invoice_id,
                timestamp=event.timestamp,
                event_type=event_type,
                actor=actor,
                detail=detail,
                summary=summary
            )

        cursor.execute("""
            INSERT INTO audit_events (event_id, invoice_id, timestamp, event_type, actor, detail, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.invoice_id,
            event.timestamp,
            event.event_type,
            event.actor,
            json.dumps(event.detail),
            event.summary
        ))
        conn.commit()

    return event


def log_from_agent_run(
    invoice_id: str,
    tool_calls_made: list[dict[str, Any]],
    db_path: str = DB_PATH
) -> list[AuditEvent]:
    """
    Takes AGENT-BRAIN's tool_calls_made output list and maps each tool call to
    the appropriate AuditEvent type, appending them to the audit trail.
    """
    events_logged = []

    for call in tool_calls_made:
        tool_name = call.get("tool_name")
        tool_input = call.get("input", {})
        result = call.get("result", {})

        if tool_name == "get_recovery_score":
            evt = log_event(
                invoice_id=invoice_id,
                event_type="INVOICE_SCORED",
                detail={"recovery_score": result.get("recovery_score", 0.0), "tier": result.get("tier", "standard")},
                actor="agent",
                db_path=db_path
            )
            events_logged.append(evt)

        elif tool_name == "get_customer_profile":
            evt = log_event(
                invoice_id=invoice_id,
                event_type="CUSTOMER_ANALYZED",
                detail={
                    "customer_id": result.get("customer_id", ""),
                    "ltv": result.get("ltv", 0.0),
                    "customer_score": result.get("customer_score", 0.0)
                },
                actor="agent",
                db_path=db_path
            )
            events_logged.append(evt)

        elif tool_name == "get_offer_recommendation":
            best_offer = result.get("best_offer")
            all_candidates = result.get("all_candidates", [])
            merchant_floor = result.get("merchant_floor", 0.0)
            rejected_count = result.get("rejected_count", 0)
            valid_count = result.get("valid_count", 0)

            # 1. Log OFFERS_EVALUATED
            evt_eval = log_event(
                invoice_id=invoice_id,
                event_type="OFFERS_EVALUATED",
                detail={"total_candidates": len(all_candidates), "valid_count": valid_count, "rejected_count": rejected_count},
                actor="agent",
                db_path=db_path
            )
            events_logged.append(evt_eval)

            # 2. Log OFFER_SELECTED if best_offer exists
            if best_offer:
                evt_sel = log_event(
                    invoice_id=invoice_id,
                    event_type="OFFER_SELECTED",
                    detail=best_offer,
                    actor="agent",
                    db_path=db_path
                )
                events_logged.append(evt_sel)

            # 3. Log OFFER_REJECTED_BELOW_FLOOR for candidates below floor
            rejected_candidates = [c for c in all_candidates if not c.get("is_valid", True)]
            for rej in rejected_candidates[:2]:  # Log top rejected samples for transparency
                rej_detail = rej.copy()
                rej_detail["merchant_floor"] = merchant_floor
                evt_rej = log_event(
                    invoice_id=invoice_id,
                    event_type="OFFER_REJECTED_BELOW_FLOOR",
                    detail=rej_detail,
                    actor="agent",
                    db_path=db_path
                )
                events_logged.append(evt_rej)

        elif tool_name == "create_payment_link":
            evt = log_event(
                invoice_id=invoice_id,
                event_type="PAYMENT_LINK_CREATED",
                detail={"amount": result.get("amount", 0.0), "payment_link_id": result.get("payment_link_id")},
                actor="agent",
                db_path=db_path
            )
            events_logged.append(evt)

        elif tool_name == "escalate_to_human":
            evt = log_event(
                invoice_id=invoice_id,
                event_type="ESCALATED_TO_HUMAN",
                detail={"reason": result.get("reason", "Escalated by agent")},
                actor="agent",
                db_path=db_path
            )
            events_logged.append(evt)

    return events_logged


def get_trail(invoice_id: str, db_path: str = DB_PATH) -> list[AuditEvent]:
    """
    Returns all audit events for a given invoice_id, sorted by timestamp ascending.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT event_id, invoice_id, timestamp, event_type, actor, detail, summary
            FROM audit_events
            WHERE invoice_id = ?
            ORDER BY timestamp ASC
        """, (invoice_id,))
        rows = cursor.fetchall()

    trail = []
    for row in rows:
        trail.append(AuditEvent(
            event_id=row[0],
            invoice_id=row[1],
            timestamp=row[2],
            event_type=row[3],
            actor=row[4],
            detail=json.loads(row[5]),
            summary=row[6]
        ))
    return trail


def get_trail_summary(invoice_id: str, db_path: str = DB_PATH) -> str:
    """
    Renders the audit trail in compact timeline format (HH:MM  summary).
    One line per event.
    """
    events = get_trail(invoice_id, db_path=db_path)
    if not events:
        return f"No audit trail events found for invoice {invoice_id}."

    lines = []
    for evt in events:
        # Extract HH:MM time from ISO timestamp (e.g., 2026-09-03T14:04:12 -> 14:04)
        try:
            dt = datetime.fromisoformat(evt.timestamp)
            time_str = dt.strftime("%H:%M")
        except Exception:
            time_str = evt.timestamp[11:16] if len(evt.timestamp) >= 16 else "00:00"

        lines.append(f"{time_str}  {evt.summary}")

    return "\n".join(lines)


if __name__ == "__main__":
    print("--- DEMO: AUDIT-TRAIL STANDALONE EXECUTION ---")

    test_inv = "INV000001"

    # Log a sequence of realistic events
    log_event(test_inv, "LEAK_DETECTED", {"segment": "UPI + Android", "impact_rupees": 150000.0}, actor="system")
    log_event(test_inv, "INVOICE_SCORED", {"recovery_score": 0.76, "tier": "high_priority"}, actor="system")
    log_event(test_inv, "CUSTOMER_ANALYZED", {"customer_id": "CUST000068", "ltv": 267600.0, "customer_score": 0.75}, actor="agent")
    log_event(test_inv, "OFFERS_EVALUATED", {"total_candidates": 35, "valid_count": 25, "rejected_count": 10}, actor="agent")
    log_event(test_inv, "OFFER_SELECTED", {"offer_amount": 106100.0, "discount_pct": 5.0, "days_to_payment": 45, "expected_value": 98121.0}, actor="agent")
    log_event(test_inv, "OFFER_REJECTED_BELOW_FLOOR", {"offer_amount": 82000.0, "discount_pct": 18.0, "merchant_floor": 85000.0}, actor="agent")
    log_event(test_inv, "PAYMENT_LINK_CREATED", {"amount": 106100.0, "payment_link_id": "plink_test_123"}, actor="system")
    log_event(test_inv, "PAYMENT_CAPTURED", {"amount_paid": 106100.0}, actor="webhook")

    print(f"\n--- TIMELINE SUMMARY FOR INVOICE {test_inv} ---")
    summary_text = get_trail_summary(test_inv)
    print(summary_text)


"""
Integration Example with API-CORE (main.py):
-------------------------------------------

from audit_trail import log_event, log_from_agent_run, get_trail, get_trail_summary

# 1. Right after run_agent() in /agent/ask or /recovery/{invoice_id}/recommend:
agent_result = run_agent(f"Recover invoice {invoice_id}")
log_from_agent_run(invoice_id, agent_result["tool_calls_made"])

# 2. In /webhooks/razorpay when payment.captured arrives:
parsed = parse_webhook_event(payload)
if parsed["invoice_id"]:
    log_event(
        invoice_id=parsed["invoice_id"],
        event_type="PAYMENT_CAPTURED",
        detail={"amount_paid": parsed["amount_paid"], "payment_link_id": parsed["payment_link_id"]},
        actor="webhook"
    )

# 3. GET /invoices/{invoice_id}/audit-trail endpoint for frontend:
@app.get("/invoices/{invoice_id}/audit-trail")
def get_invoice_audit_trail(invoice_id: str):
    return {
        "invoice_id": invoice_id,
        "timeline_summary": get_trail_summary(invoice_id),
        "events": get_trail(invoice_id)
    }
"""
