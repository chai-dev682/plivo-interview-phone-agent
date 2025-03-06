from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class InterviewRequest(BaseModel):
    job_id: str
    phone_number: str
    questions: List[str]
    evaluation_criteria: List[str]
    interview_language: str # en, es, fr ...
    evaluation_language: str # en, es, fr ...

class Interview(InterviewRequest):
    interview_id: str
    is_completed: bool = False
    created_at: datetime

class InterviewResponseData(BaseModel):
    interview_id: str
    job_id: str
    phone_number: str
    is_completed: bool
    created_at: datetime

class InterviewResponse(BaseModel):
    success: bool
    message: str
    data: Optional[InterviewResponseData] = None
