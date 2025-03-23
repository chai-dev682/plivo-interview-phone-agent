from typing import List, Dict
from langchain_community.chat_message_histories import ChatMessageHistory

from app.core.logger import logger
from app.core.prompt_templates.evaluation import evaluation_prompt
from app.services.chat import chat_service
from app.utils.utils import format_conversation_history
from app.core import state

class EvaluationService:
    def __init__(self):
        pass

    async def evaluate_interview(
        self,
        messages: ChatMessageHistory,
        criteria: List[str],
        evaluation_language: str,
        job_id: str,
        phone_number: str,
        call_recording_url: str
    ) -> Dict:
        try:
            evaluation = chat_service.function_call(evaluation_prompt.format(
                messages=messages,
                criteria=criteria,
                evaluation_language=evaluation_language
            ), "evaluate_interview")

            logger.info(f"Evaluation: {evaluation}")

            # TODO: Uncomment this when webhook is ready
            await self.send_webhook(job_id, phone_number, call_recording_url, messages, evaluation)
            
        except Exception as e:
            logger.error(f"Error evaluating interview: {str(e)}")
            raise

    async def send_webhook(self, job_id: str, phone_number: str, call_recording_url: str, messages: ChatMessageHistory, evaluation_data: Dict):
        try:
            # TODO: Customize webhook sending function here
            import aiohttp
            
            # TODO: Get webhook URL from environment variable or other source
            webhook_url = state.admin_config.get("webhook_url") or f"https://webhook.site/21742565-ba62-4ce6-ab62-83bab0924b1c"

            # Prepare the payload
            payload = {
                "job_id": job_id,
                "phone_number": phone_number,
                "call_recording_url": call_recording_url,
                "evaluation": evaluation_data,
                "call_transcript": format_conversation_history(messages)
            }
            print("webhook evaluation payload: ",payload)

            # Send POST request to webhook URL
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status not in (200, 201, 202):
                        logger.error(f"Webhook request failed with status {response.status}")
                        raise Exception(f"Webhook request failed with status {response.status}")
                    
                    logger.info(f"Webhook sent successfully to {webhook_url}")
                    
        except Exception as e:
            logger.error(f"Error sending webhook: {str(e)}")
            raise

evaluation_service = EvaluationService()