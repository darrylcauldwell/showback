from fastapi import APIRouter

from app.services.whatif import compare_providers

router = APIRouter(prefix="/api/whatif", tags=["whatif"])


@router.get("/compare")
async def compare():
    """Compare current hosting cost against equivalent cloud offerings."""
    return compare_providers()
