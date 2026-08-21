import uuid
import pytest
from pydantic import ValidationError

from app.schemas.auth import UserRegister, UserLogin
from app.schemas.vendor import VendorCreate, VendorDropdown
from app.schemas.product import GoldenReferenceCreate
from app.schemas.inspection import InspectionCreate, InspectionReviewRequest
from app.models.user import UserRole
from app.models.inspection import InspectionVerdict, PolicyAction, ReviewDecision


def test_user_schemas_validation():
    # Valid register
    user = UserRegister(email="analyst@visionforge.ai", password="StrongPassword123", full_name="Inspection Analyst")
    assert user.email == "analyst@visionforge.ai"

    # Invalid short password
    with pytest.raises(ValidationError):
        UserRegister(email="analyst@visionforge.ai", password="123", full_name="Inspection Analyst")


def test_vendor_schemas_validation():
    vendor = VendorCreate(name="Foxconn Precision", site_name="Shenzhen Facility", code="VND-FOX-01")
    assert vendor.code == "VND-FOX-01"

    dropdown = VendorDropdown(id=uuid.uuid4(), name=vendor.name, site_name=vendor.site_name, code=vendor.code)
    assert dropdown.code == "VND-FOX-01"


def test_product_schemas_validation():
    prod = GoldenReferenceCreate(
        part_id="PCB-MCU-V2",
        part_name="Microcontroller Board V2",
        vendor_id=uuid.uuid4(),
        viewing_angle="front",
        image_path="/data/golden_images/mcu_v2_front.jpg",
        description="Master golden reference",
    )
    assert prod.part_id == "PCB-MCU-V2"


def test_inspection_schemas_validation():
    insp_create = InspectionCreate(vendor_id=uuid.uuid4(), location="Bangalore Hub")
    assert insp_create.location == "Bangalore Hub"

    review_req = InspectionReviewRequest(review_decision="approved", reviewer_comment="Matches all physical checks")
    assert review_req.review_decision == "approved"
