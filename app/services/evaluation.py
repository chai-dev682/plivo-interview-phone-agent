from typing import List, Dict
from langchain_community.chat_message_histories import ChatMessageHistory

from app.core.logger import logger
from app.services.chat import chat_service
from app.core.prompt_templates.evaluation import evaluation_prompt

class EvaluationService:
    def __init__(self):
        pass

    async def evaluate_interview(
        self,
        messages: ChatMessageHistory,
        criteria: List[str],
        evaluation_language: str
    ) -> Dict:
        try:
            evaluation = chat_service.function_call(evaluation_prompt.format(
                messages=messages,
                criteria=criteria,
                evaluation_language=evaluation_language
            ), "evaluate_interview")

            logger.info(f"Evaluation: {evaluation}")
            
        except Exception as e:
            logger.error(f"Error evaluating interview: {str(e)}")
            raise

    async def send_webhook(self, evaluation_data: Dict, webhook_url: str):
        try:
            # TODO: Implement webhook sending logic
            pass
        except Exception as e:
            logger.error(f"Error sending webhook: {str(e)}")
            raise

evaluation_service = EvaluationService()