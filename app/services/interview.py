from typing import List, Optional
from app.core.logger import logger
from app.schemas.interview import InterviewCreate, InterviewUpdate, Interview, InterviewResponse, InterviewResponseData
from app.services.mysql import mysql_service

class InterviewService:
    def __init__(self):
        pass

    async def create_interview(self, request: InterviewCreate) -> InterviewResponse:
        try:
            interview = Interview(
                interview_id=1,
                job_id=request.job_id,
                phone_number=request.phone_number,
                questions=request.questions,
                evaluation_criteria=request.evaluation_criteria,
                interview_language=request.interview_language,
                evaluation_language=request.evaluation_language
            )
            
            res = await mysql_service.insert_interview(interview)
            
            return InterviewResponse(
                success=True,
                message="Interview created successfully",
                data=InterviewResponseData(
                    interview_id=res,
                    job_id=interview.job_id,
                    phone_number=interview.phone_number,
                    is_completed=interview.is_completed,
                    created_at=interview.created_at
                )
            )
        except Exception as e:
            logger.error(f"Error creating interview: {str(e)}")
            return InterviewResponse(
                success=False,
                message=f"Interview creation failed: {str(e)}"
            )

    async def get_interview(self, interview_id: int) -> Optional[Interview]:
        try:
            interview = await mysql_service.get_interview(interview_id)
            if not interview:
                return None
            return Interview.model_validate(interview)
        except Exception as e:
            logger.error(f"Error getting interview: {str(e)}")
            raise

    async def update_interview(self, interview_id: int, update_data: InterviewUpdate) -> Optional[Interview]:
        try:
            # First get the existing interview
            existing = await self.get_interview(interview_id)
            if not existing:
                return None

            # Update only the fields that are provided
            update_dict = update_data.model_dump(exclude_unset=True)
            updated_interview = await mysql_service.update_interview(interview_id, update_dict)
            
            return Interview.model_validate(updated_interview) if updated_interview else None
        except Exception as e:
            logger.error(f"Error updating interview: {str(e)}")
            raise

    async def delete_interview(self, interview_id: int) -> bool:
        try:
            return await mysql_service.delete_interview(interview_id)
        except Exception as e:
            logger.error(f"Error deleting interview: {str(e)}")
            raise

    async def get_interviews_by_phone(self, phone_number: str) -> List[Interview]:
        try:
            interviews = await mysql_service.get_interviews_by_phone(phone_number)
            return [Interview.model_validate(interview) for interview in interviews]
        except Exception as e:
            logger.error(f"Error getting interviews by phone: {str(e)}")
            raise
        
    async def get_interview_by_phone(self, phone_number: str) -> Optional[Interview]:
        try:
            interview = await mysql_service.get_interview_by_phone(phone_number)
            return Interview.model_validate(interview) if interview else None
        except Exception as e:
            logger.error(f"Error getting interview by phone: {str(e)}")
            raise
    
    async def update_interview_by_job_id(self, job_id: str, interview_id: int, update_data: InterviewUpdate) -> Optional[Interview]:
        try:
            # Update only the fields that are provided
            update_dict = update_data.model_dump(exclude_unset=True)
            updated_interview = await mysql_service.update_interview_by_job_id(job_id, interview_id, update_dict)
            return Interview.model_validate(updated_interview) if updated_interview else None
        except Exception as e:
            logger.error(f"Error updating interview by job ID: {str(e)}")
            raise

interview_service = InterviewService()
