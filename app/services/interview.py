import uuid
from datetime import datetime
from app.core.logger import logger
from app.schemas.interview import InterviewRequest, InterviewResponse, InterviewResponseData, Interview
from app.services.mysql import mysql_service

class InterviewService:
    def __init__(self):
        pass

    async def schedule_interview(self, request: InterviewRequest):
        try:
            interview = Interview(
                interview_id=str(uuid.uuid4()),
                job_id=request.job_id,
                phone_number=request.phone_number,
                questions=request.questions,
                evaluation_criteria=request.evaluation_criteria,
                interview_language=request.interview_language,
                evaluation_language=request.evaluation_language,
                is_completed=False,
                created_at=datetime.now(datetime.UTC)
            )
            
            await mysql_service.insert_interview(interview)
            
            return InterviewResponse(
                success=True,
                message="Interview scheduled successfully",
                data=InterviewResponseData(
                    interview_id=interview.interview_id,
                    job_id=request.job_id,
                    phone_number=request.phone_number,
                    is_completed=False,
                    created_at=interview.created_at
                )
            )
        except Exception as e:
            logger.error(f"Error scheduling interview: {str(e)}")
            return InterviewResponse(
                success=False,
                message=f"Interview schedule failed: {str(e)}"
            )
    
    async def get_interview(self, interview_id: str):
        try:
            interview = await mysql_service.get_interview(interview_id)
            return interview
        except Exception as e:
            logger.error(f"Error getting interview: {str(e)}")
            raise

interview_service = InterviewService()
