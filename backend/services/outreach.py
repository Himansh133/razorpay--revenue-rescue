import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.config import (
    RESEND_API_KEY,
    OUTREACH_FROM_EMAIL,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER,
    is_email_configured,
    is_sms_configured
)
from backend.db.database import SessionLocal, log_event
from backend.db.models import OutreachRecordModel

try:
    import resend
    HAS_RESEND = True
except ImportError:
    HAS_RESEND = False

try:
    from twilio.rest import Client as TwilioClient
    HAS_TWILIO = True
except ImportError:
    HAS_TWILIO = False


def check_duplicate_outreach(db: Session, invoice_id: str, channel: str) -> Optional[Dict[str, Any]]:
    """
    Checks if a successful outreach attempt already exists for this invoice and channel.
    """
    existing = db.query(OutreachRecordModel).filter(
        OutreachRecordModel.invoice_id == invoice_id,
        OutreachRecordModel.channel == channel,
        OutreachRecordModel.status == "sent"
    ).first()

    if existing:
        return {
            "status": "already_sent",
            "channel": channel,
            "recipient": existing.recipient,
            "provider": existing.provider,
            "message_id": existing.provider_message_id
        }
    return None


def send_recovery_email(
    invoice_id: str,
    customer_id: str,
    customer_name: str,
    recipient_email: str,
    original_amount: float,
    offer_amount: float,
    discount_pct: float,
    payment_terms_days: int,
    payment_url: str
) -> Dict[str, Any]:
    """
    Sends transactional recovery offer email using Resend API with strict financial state preservation.
    """
    if not recipient_email or not recipient_email.strip() or "@" not in recipient_email:
        return {
            "status": "unavailable",
            "channel": "email",
            "recipient": recipient_email,
            "error": "Recipient email address is missing or invalid"
        }

    db: Session = SessionLocal()
    try:
        dup = check_duplicate_outreach(db, invoice_id, "email")
        if dup:
            return dup

        savings = max(0.0, original_amount - offer_amount)
        subject = f"Payment option available for Invoice {invoice_id}"
        
        email_body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; color: #1e293b; padding: 20px;">
            <h2 style="color: #0f172a;">Payment Option for Invoice {invoice_id}</h2>
            <p>Hi {customer_name},</p>
            <p>We noticed that invoice <strong>{invoice_id}</strong> is currently outstanding.</p>
            <p>We have prepared an optimized recovery payment option for you:</p>
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
                <p style="margin: 4px 0;"><strong>Original Invoice Amount:</strong> ₹{original_amount:,.2f}</p>
                <p style="margin: 4px 0; color: #16a34a;"><strong>Recovery Offer Amount:</strong> ₹{offer_amount:,.2f}</p>
                <p style="margin: 4px 0; color: #16a34a;"><strong>Savings:</strong> ₹{savings:,.2f} ({discount_pct:.1f}% discount)</p>
                <p style="margin: 4px 0;"><strong>Payment Terms:</strong> {payment_terms_days} Days</p>
            </div>
            <p>You can review and complete the payment securely below:</p>
            <div style="margin: 24px 0;">
                <a href="{payment_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Pay Securely Now</a>
            </div>
            <p style="word-break: break-all; font-size: 13px; color: #64748b;">Direct link: <a href="{payment_url}">{payment_url}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
            <p style="font-size: 13px; color: #64748b;">Thank you,<br/><strong>Revenue Rescue Engine</strong></p>
        </div>
        """

        email_body_text = f"""Hi {customer_name},

We noticed that invoice {invoice_id} is still outstanding.

We've prepared a recovery payment option for you:

Original invoice amount: ₹{original_amount:,.2f}
Recovery offer: ₹{offer_amount:,.2f}
Savings: ₹{savings:,.2f} ({discount_pct:.1f}% discount)
Payment terms: {payment_terms_days} days

You can review and complete the payment securely here:
{payment_url}

Thank you,
Revenue Rescue
"""

        if is_email_configured() and HAS_RESEND:
            try:
                resend.api_key = RESEND_API_KEY
                res = resend.Emails.send({
                    "from": OUTREACH_FROM_EMAIL,
                    "to": [recipient_email],
                    "subject": subject,
                    "html": email_body_html,
                    "text": email_body_text
                })
                msg_id = str(res.get("id", "")) if isinstance(res, dict) else str(getattr(res, "id", ""))
                
                record = OutreachRecordModel(
                    invoice_id=invoice_id,
                    customer_id=customer_id,
                    channel="email",
                    recipient=recipient_email,
                    status="sent",
                    provider="resend",
                    provider_message_id=msg_id
                )
                db.add(record)
                db.commit()

                log_event(
                    invoice_id=invoice_id,
                    event_type="EMAIL_SENT",
                    detail={"recipient": recipient_email, "provider": "resend", "message_id": msg_id}
                )

                return {
                    "status": "sent",
                    "channel": "email",
                    "recipient": recipient_email,
                    "provider": "resend",
                    "message_id": msg_id
                }
            except Exception as err:
                err_msg = str(err)
                record = OutreachRecordModel(
                    invoice_id=invoice_id,
                    customer_id=customer_id,
                    channel="email",
                    recipient=recipient_email,
                    status="failed",
                    provider="resend",
                    error=err_msg
                )
                db.add(record)
                db.commit()

                log_event(
                    invoice_id=invoice_id,
                    event_type="OUTREACH_FAILED",
                    detail={"channel": "email", "reason": err_msg}
                )

                return {
                    "status": "failed",
                    "channel": "email",
                    "recipient": recipient_email,
                    "provider": "resend",
                    "error": err_msg
                }
        else:
            # Resend key unconfigured fallback: record as unavailable / unconfigured
            record = OutreachRecordModel(
                invoice_id=invoice_id,
                customer_id=customer_id,
                channel="email",
                recipient=recipient_email,
                status="unavailable",
                provider="resend",
                error="RESEND_API_KEY not configured"
            )
            db.add(record)
            db.commit()

            return {
                "status": "unavailable",
                "channel": "email",
                "recipient": recipient_email,
                "provider": "resend",
                "error": "RESEND_API_KEY is not configured"
            }
    finally:
        db.close()


def send_recovery_sms(
    invoice_id: str,
    customer_id: str,
    recipient_phone: str,
    offer_amount: float,
    payment_url: str
) -> Dict[str, Any]:
    """
    Sends concise recovery offer SMS using Twilio API with strict financial state preservation.
    """
    if not recipient_phone or not recipient_phone.strip():
        return {
            "status": "unavailable",
            "channel": "sms",
            "recipient": recipient_phone,
            "error": "Recipient phone number is missing or invalid"
        }

    db: Session = SessionLocal()
    try:
        dup = check_duplicate_outreach(db, invoice_id, "sms")
        if dup:
            return dup

        sms_message = f"Revenue Rescue: Invoice {invoice_id} has a recovery payment option of ₹{offer_amount:,.0f}. Pay securely: {payment_url}"

        if is_sms_configured() and HAS_TWILIO:
            try:
                client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                message = client.messages.create(
                    body=sms_message,
                    from_=TWILIO_FROM_NUMBER,
                    to=recipient_phone
                )
                msg_sid = str(message.sid)

                record = OutreachRecordModel(
                    invoice_id=invoice_id,
                    customer_id=customer_id,
                    channel="sms",
                    recipient=recipient_phone,
                    status="sent",
                    provider="twilio",
                    provider_message_id=msg_sid
                )
                db.add(record)
                db.commit()

                log_event(
                    invoice_id=invoice_id,
                    event_type="SMS_SENT",
                    detail={"recipient": recipient_phone, "provider": "twilio", "message_id": msg_sid}
                )

                return {
                    "status": "sent",
                    "channel": "sms",
                    "recipient": recipient_phone,
                    "provider": "twilio",
                    "message_id": msg_sid
                }
            except Exception as err:
                err_msg = str(err)
                record = OutreachRecordModel(
                    invoice_id=invoice_id,
                    customer_id=customer_id,
                    channel="sms",
                    recipient=recipient_phone,
                    status="failed",
                    provider="twilio",
                    error=err_msg
                )
                db.add(record)
                db.commit()

                log_event(
                    invoice_id=invoice_id,
                    event_type="OUTREACH_FAILED",
                    detail={"channel": "sms", "reason": err_msg}
                )

                return {
                    "status": "failed",
                    "channel": "sms",
                    "recipient": recipient_phone,
                    "provider": "twilio",
                    "error": err_msg
                }
        else:
            record = OutreachRecordModel(
                invoice_id=invoice_id,
                customer_id=customer_id,
                channel="sms",
                recipient=recipient_phone,
                status="unavailable",
                provider="twilio",
                error="Twilio credentials not configured"
            )
            db.add(record)
            db.commit()

            return {
                "status": "unavailable",
                "channel": "sms",
                "recipient": recipient_phone,
                "provider": "twilio",
                "error": "Twilio credentials are not configured"
            }
    finally:
        db.close()
