from langchain_core.messages import SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory

def format_conversation_history(messages: ChatMessageHistory) -> str:
    return "\n".join([f"{msg.type}: {msg.content}" for msg in messages.messages if not isinstance(msg, SystemMessage)])

