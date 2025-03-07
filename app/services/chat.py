from langchain_core.messages import BaseMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import ChatOpenAI
from typing import List

from app.core.config import settings, ModelType


class ChatService:
    def __init__(self):
        self.model = ChatOpenAI(
            model=ModelType.GPT4O,
            openai_api_key=settings.openai_api_key
        )

    async def chat(self, messages: ChatMessageHistory | List[BaseMessage]) -> str:
        response = self.model.invoke(messages)
        return response.content
    
    # def function_call(self, prompt, function_name):
    #     model_ = self.model.bind_tools(functions, tool_choice=function_name)
    #     messages = [SystemMessage(prompt)]
    #     function_call = model_.invoke(messages).tool_calls
    #     result = function_call[0]['args']

    #     return result

chat_service = ChatService()