import uuid
import pytest
from app.shared.memory import (
    WorkingMemory,
    WorkingMemoryRegistry,
)


def test_working_memory_lifecycle():
    inspection_id = uuid.uuid4()
    memory = WorkingMemory(
        inspection_id=inspection_id,
        vendor_id=uuid.uuid4(),
        location="Plant-A",
    )

    # Initial state
    assert memory.quality_passed is None
    assert memory.authenticity_flagged is False

    # Simulate Stage 1 output
    memory.quality_passed = True
    assert memory.quality_passed is True

    # Simulate Stage 3 output
    memory.similarity_score = 0.94
    assert memory.similarity_score == 0.94


@pytest.mark.asyncio
async def test_working_memory_registry():
    registry = WorkingMemoryRegistry()
    inspection_id = uuid.uuid4()

    # Get or create
    mem = await registry.get_or_create(inspection_id)
    assert mem.inspection_id == inspection_id

    # Retrieve again
    mem_again = await registry.get(inspection_id)
    assert mem_again is mem

    # Cleanup
    await registry.release(inspection_id)
    assert await registry.get(inspection_id) is None
