from langchain_core.messages import BaseMessage, SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import ChatOpenAI
from typing import List

from app.core.config import settings, ModelType
from app.core.function_templates.functions import functions

class ChatService:
    def __init__(self):
        self.model = ChatOpenAI(
            model=ModelType.GPT4O,
            openai_api_key=settings.openai_api_key
        )

    async def chat(self, messages: ChatMessageHistory | List[BaseMessage]) -> str:
        # If messages is ChatMessageHistory, get the messages list
        if isinstance(messages, ChatMessageHistory):
            messages = messages.messages
        
        response = self.model.invoke(messages)
        print(f"LLM Response: {response.content}")
        return response.content
    
    def function_call(self, prompt, function_name):
        model_ = self.model.bind_tools(functions, tool_choice=function_name)
        messages = [SystemMessage(prompt)]
        function_call = model_.invoke(messages).tool_calls
        result = function_call[0]['args']

        return result

chat_service = ChatService()