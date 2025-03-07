from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

class InterviewBase(BaseModel):
    job_id: str
    phone_number: str
    questions: List[str]
    evaluation_criteria: List[str]
    interview_language: str # en, es, fr ...
    evaluation_language: str # en, es, fr ...
    call_recording_url: Optional[str] = None

class InterviewCreate(InterviewBase):
    pass

class InterviewUpdate(BaseModel):
    job_id: Optional[str] = None
    phone_number: Optional[str] = None
    questions: Optional[List[str]] = None
    evaluation_criteria: Optional[List[str]] = None
    interview_language: Optional[str] = None
    evaluation_language: Optional[str] = None
    is_completed: Optional[bool] = None
    call_recording_url: Optional[str] = None

class Interview(InterviewBase):
    interview_id: int
    is_completed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        from_attributes = True

class InterviewResponseData(BaseModel):
    interview_id: int
    job_id: str
    phone_number: str
    is_completed: bool
    created_at: datetime

class InterviewResponse(BaseModel):
    success: bool
    message: str
    data: Optional[InterviewResponseData] = None
