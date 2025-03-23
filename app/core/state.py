# app/core/state.py
from app.core.config import settings


admin_config = {
    "plivo_auth_id": settings.auth_id or "",
    "plivo_auth_token": settings.auth_token or "",
    "welcome_message": (
                            "Say: 'Hello! I'm a recruiter, and I will be conducting your interview today. Can you please tell me your name?' "
                            "Use a warm, professional tone. Keep it brief and welcoming. "
                            "Do not mention anything about being an assistant or AI model."
                        ) or "",
    "prompt": (
        "Introduce yourself briefly as a recruiter. Ask for the candidate's name. "
        "Then ask each question from the list below one by one. "
        "Do not provide feedback or follow-up questions. Just ask the next question after the candidate responds. "
        "After all questions are asked, thank the candidate and end the call."
        ) or "",
    "voice": "alloy",  # default
    "webhook_url": "https://webhook.site/21742565-ba62-4ce6-ab62-83bab0924b1c"
}

