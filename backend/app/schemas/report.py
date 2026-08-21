from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: uuid.UUID
    case_number: str
    vendor_name: str
    location: str
    verdict: str
    fraud_probability: Optional[float] = None
    fraud_category: Optional[str] = None
    policy_action: Optional[str] = None
    report_path: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
