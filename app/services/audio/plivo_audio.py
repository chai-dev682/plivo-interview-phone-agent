import asyncio
import base64
import json
from fastapi import WebSocket
from elevenlabs.conversational_ai.conversation import AudioInterface
from starlette.websockets import WebSocketDisconnect, WebSocketState
import logging

logger = logging.getLogger(__name__)

class PlivoAudioInterface(AudioInterface):
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.input_callback = None
        self.streamId = None
        self.loop = asyncio.get_event_loop()

    def start(self, input_callback):
        self.input_callback = input_callback

    def stop(self):
        self.input_callback = None
        self.streamId = None

    def output(self, audio: bytes):
        """
        This method should return quickly and not block the calling thread.
        """
        asyncio.run_coroutine_threadsafe(self.send_audio_to_plivo(audio), self.loop)

    def interrupt(self):
        asyncio.run_coroutine_threadsafe(self.send_clear_message_to_plivo(), self.loop)

    async def send_audio_to_plivo(self, audio: bytes):
        if self.streamId:
            try:
                if self.websocket.application_state == WebSocketState.CONNECTED:
                    audio_payload = base64.b64encode(audio).decode("utf-8")
                    audio_message = {
                        "event": "playAudio",
                        "media": {
                            "contentType": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "payload": audio_payload
                        }
                    }
                    await self.websocket.send_text(json.dumps(audio_message))
            except (WebSocketDisconnect, RuntimeError):
                pass

    async def send_clear_message_to_plivo(self):
        if self.streamId:
            clear_message = {
                "event": "clearAudio",
                "streamSid": self.streamId
            }
            try:
                if self.websocket.application_state == WebSocketState.CONNECTED:
                    await self.websocket.send_text(json.dumps(clear_message))
            except (WebSocketDisconnect, RuntimeError):
                pass

    async def handle_plivo_message(self, data):
        try:
            event_type = data.get("event")
            if event_type == "start":
                self.streamId = data["start"]["streamId"]
            elif event_type == "media":
                audio_data = base64.b64decode(data["media"]["payload"])

                if self.input_callback:
                    self.input_callback(audio_data)
        except Exception as e:
            logger.error(f"Error handling Plivo message: {e}")
            raise
