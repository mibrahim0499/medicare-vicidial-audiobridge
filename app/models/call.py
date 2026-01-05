"""Call data models"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class CallStatus(str, Enum):
    """Call status enumeration"""
    INITIATING = "initiating"
    RINGING = "ringing"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TRANSFERRED = "transferred"


class CallBase(BaseModel):
    """Base call model"""
    call_id: str = Field(..., description="Unique call identifier")
    channel_id: Optional[str] = Field(None, description="Asterisk channel ID")
    caller_number: Optional[str] = Field(None, description="Caller phone number")
    callee_number: Optional[str] = Field(None, description="Callee phone number")
    campaign_id: Optional[str] = Field(None, description="VICIdial campaign ID")
    status: CallStatus = Field(CallStatus.INITIATING, description="Call status")
    start_time: Optional[datetime] = Field(None, description="Call start timestamp")
    end_time: Optional[datetime] = Field(None, description="Call end timestamp")
    duration: Optional[int] = Field(None, description="Call duration in seconds")


class CallCreate(CallBase):
    """Call creation model"""
    pass


class CallUpdate(BaseModel):
    """Call update model"""
    status: Optional[CallStatus] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    channel_id: Optional[str] = None


class Call(CallBase):
    """Call model with ID"""
    id: Optional[int] = Field(None, description="Database ID")
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Record update timestamp")
    
    class Config:
        from_attributes = True

