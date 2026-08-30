# backend/app/models/__init__.py
# Re-export all models so that `import app.models` registers every table's
# metadata on the shared Base — required for init_db()/Alembic autogenerate.
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.product import GoldenReference
from app.models.inspection import (
    Inspection,
    InspectionStatus,
    InspectionVerdict,
    PolicyAction,
    ReviewDecision,
)
from app.models.evidence import AgentType, Evidence

__all__ = [
    "User",
    "UserRole",
    "Vendor",
    "GoldenReference",
    "Inspection",
    "InspectionStatus",
    "InspectionVerdict",
    "PolicyAction",
    "ReviewDecision",
    "AgentType",
    "Evidence",
]

