import datetime
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class AuditEvent(BaseModel):
    event_id: str
    invoice_id: str
    timestamp: str
    event_type: str
    actor: str = "system"
    detail: Dict[str, Any] = Field(default_factory=dict)
    summary: str
