from openai import OpenAI

from app.core.config import settings, ModelType


class ChatService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    async def chat(self, messages: list) -> str:
        response = self.client.chat.completions.create(
            model=ModelType.GPT4O,
            messages=messages
        )

        response = response.choices[0].message.content
        return response

chat_service = ChatService()