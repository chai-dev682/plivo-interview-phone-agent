from fastapi import APIRouter, HTTPException, status
from typing import List

from app.services.interview import interview_service
from app.schemas.interview import (
    InterviewCreate,
    InterviewUpdate,
    Interview,
    InterviewResponse
)

router = APIRouter(
    prefix="/api/v1",
    tags=["interviews"]
)

@router.post("/interviews", response_model=InterviewResponse)
async def create_interview(request: InterviewCreate):
    """Create a new interview"""
    response = await interview_service.create_interview(request)
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )
    return response

@router.get("/interviews/{interview_id}", response_model=Interview)
async def get_interview(interview_id: int):
    """Get an interview by ID"""
    interview = await interview_service.get_interview(interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found"
        )
    return interview

@router.put("/interviews/{interview_id}", response_model=Interview)
async def update_interview(interview_id: int, update_data: InterviewUpdate):
    """Update an interview"""
    updated = await interview_service.update_interview(interview_id, update_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found"
        )
    return updated

@router.put("/jobs/{job_id}/interviews/{interview_id}", response_model=Interview)
async def update_interview_by_job_id(job_id: str, interview_id: int, request: InterviewUpdate):
    """Update an interview by job ID"""
    interview = await interview_service.update_interview_by_job_id(job_id, interview_id, request)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found"
        )
    return interview

@router.delete("/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview(interview_id: int):
    """Delete an interview"""
    success = await interview_service.delete_interview(interview_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found"
        )

@router.get("/interviews/phone/{phone_number}", response_model=List[Interview])
async def get_interviews_by_phone(phone_number: str):
    """Get all interviews for a phone number"""
    return await interview_service.get_interviews_by_phone(phone_number)