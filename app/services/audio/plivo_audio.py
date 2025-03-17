import asyncio
import base64
import json
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
import logging
from openai import OpenAI
from app.core.config import settings,ModelType

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=settings.openai_api_key,
)  # Initialize OpenAI Client

class PlivoAudioInterface:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.input_callback = None
        self.streamId = None
        self.loop = asyncio.get_event_loop()

    def start(self, input_callback):
        """Start processing incoming speech data from Plivo WebSocket."""
        self.input_callback = input_callback

    def stop(self):
        """Stop processing and clear the stream ID."""
        self.input_callback = None
        self.streamId = None

    def output(self, audio: bytes):
        """
        Sends AI-generated speech to Plivo WebSocket.
        """
        asyncio.run_coroutine_threadsafe(self.send_audio_to_plivo(audio), self.loop)

    def interrupt(self):
        """Interrupts ongoing speech playback by sending a clear command to Plivo."""
        asyncio.run_coroutine_threadsafe(self.send_clear_message_to_plivo(), self.loop)

    async def send_audio_to_plivo(self, text: str):
        """
        Converts AI-generated text into speech using OpenAI TTS and sends it to Plivo WebSocket.
        """
        if self.streamId:
            try:
                if self.websocket.application_state == WebSocketState.CONNECTED:
                    # Convert text to speech using OpenAI
                    response = client.audio.speech.create(
                        model="tts-1",
                        voice="alloy",  # Available voices: alloy, echo, fable, onyx, nova, shimmer
                        input=text,
                    )

                    # Encode the audio into Base64 format
                    audio_bytes = response.content
                    encoded_audio = base64.b64encode(audio_bytes).decode("utf-8")

                    # Prepare and send the message to Plivo WebSocket
                    audio_message = {
                        "event": "playAudio",
                        "media": {
                            "contentType": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "payload": encoded_audio
                        }
                    }
                    await self.websocket.send_text(json.dumps(audio_message))

            except (WebSocketDisconnect, RuntimeError) as e:
                logger.error(f"Error sending OpenAI TTS audio to Plivo: {e}")

    async def send_clear_message_to_plivo(self):
        """Clears the current audio playback on Plivo."""
        if self.streamId:
            clear_message = {
                "event": "clearAudio",
                "streamSid": self.streamId
            }
            try:
                if self.websocket.application_state == WebSocketState.CONNECTED:
                    await self.websocket.send_text(json.dumps(clear_message))
            except (WebSocketDisconnect, RuntimeError) as e:
                logger.error(f"Error clearing audio on Plivo: {e}")

    async def handle_plivo_message(self, data):
        """
        Handles incoming messages from Plivo WebSocket.
        Processes audio data and transmits it to the AI model if needed.
        """
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
