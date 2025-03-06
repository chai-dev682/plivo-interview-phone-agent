from fastapi import APIRouter, HTTPException
from app.services.interview import interview_service
from app.schemas.interview import InterviewRequest

router = APIRouter()

@router.post("/schedule_interview")
async def schedule_interview(request: InterviewRequest):
    try:
        return await interview_service.schedule_interview(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/interview/{interview_id}")
async def get_interview(interview_id: str):
    try:
        return await interview_service.get_interview(interview_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))