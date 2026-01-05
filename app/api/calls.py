"""Call management endpoints"""

from fastapi import APIRouter, HTTPException
from typing import List
from app.services.logger import LoggingService

router = APIRouter()
logging_service = LoggingService()


@router.get("/calls", response_model=List[dict])
async def get_calls(limit: int = 100):
    """Get call history"""
    try:
        calls = await logging_service.get_call_history(limit=limit)
        return calls
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls/{call_id}")
async def get_call(call_id: str):
    """Get specific call details"""
    try:
        calls = await logging_service.get_call_history(limit=1000)
        call = next((c for c in calls if c["call_id"] == call_id), None)
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        return call
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

