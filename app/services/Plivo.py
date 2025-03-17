import asyncio
import base64
import json
import websockets
import traceback
from openai import OpenAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.chat_message_histories import ChatMessageHistory
import starlette.websockets

from app.core.config import settings
from app.core.logger import logger
from app.services.chat import chat_service
from app.services.interview import interview_service
from app.services.evaluation import evaluation_service
from app.services.callRecord import call_record_service
from app.services.audio.plivo_audio import PlivoAudioInterface
from app.core.prompt_templates.call_ended import call_ended_prompt
from app.utils.utils import format_conversation_history
from app.schemas.interview import InterviewUpdate

client = OpenAI(api_key=settings.openai_api_key)

class PlivoService:
    def __init__(self):
        self.messages = ChatMessageHistory()
        self.ping_interval = 25  # seconds
        # Initialize event loop in the main thread
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    async def text_to_speech_file(self, text: str, end_call: bool = False):
        """Convert text to speech using OpenAI and send it via Plivo WebSocket."""
        try:
            response = client.audio.speech.create(
                model="tts-1",  # OpenAI's TTS model
                voice="alloy",  # Available voices: alloy, echo, fable, onyx, nova, shimmer
                input=text,
            )

            # Stream AI-generated speech to Plivo
            audio_bytes = response.content
            encoded_audio = base64.b64encode(audio_bytes).decode("utf-8")

            audio_message = {
                "event": "playAudio",
                "media": {
                    "contentType": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "payload": encoded_audio
                }
            }

            await self.plivo_ws.send_text(json.dumps(audio_message))

            if end_call:
                await asyncio.sleep(4)  # Give time for audio to finish playing
                try:
                    if self.plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
                        await self.plivo_ws.close(code=1000)  # Normal closure
                    logger.info("Clearing messages...")
                    self.messages.clear()
                except Exception as e:
                    logger.error(f"Error during graceful shutdown: {e}")

        except Exception as e:
            logger.error(f"Error in OpenAI TTS: {e}")

    async def generate_ai_response(self, text: str) -> str:
        """Generates AI response using OpenAI GPT-4."""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an AI interview assistant. Conduct the interview professionally."},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "I'm sorry, I couldn't process that."

    def handle_transcript(self, transcription):
        """Handles incoming transcription from Deepgram."""
        print(f"Transcription: {transcription}")
        self.messages.add_user_message(HumanMessage(transcription))
    
    async def handle_agent_response(self, text):
        """Handles AI response and checks if call should end."""
        print(f"Agent response: {text}")
        self.messages.add_ai_message(AIMessage(text))

        if len(self.messages.messages) < 5:
            return

        call_ended = chat_service.function_call(call_ended_prompt.format(
            transcript=format_conversation_history(self.messages)
        ), "call_ended")

        if call_ended["call_ended"]:
            logger.info("Call ended")
            if self.call_record:
                call_record_service.stop_recording(self.call_record['call_uuid'])
            
            await evaluation_service.evaluate_interview(
                self.messages, 
                self.criteria, 
                self.evaluation_language, 
                self.interview.job_id, 
                self.from_number, 
                self.call_record['url'] if self.call_record else None
            )
            
            await interview_service.update_interview(
                self.interview.interview_id, 
                InterviewUpdate(
                    is_completed=True, 
                    call_recording_url=self.call_record['url'] if self.call_record else None
                )
            )
            
            logger.info("Clearing messages...")
            self.messages.clear()
            try:
                if self.plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
                    await self.plivo_ws.close(code=1000)  # Normal closure
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")

    async def plivo_receiver(self, plivo_ws, from_number: str, call_uuid: str = None):
        """Handles incoming WebSocket connection from Plivo and manages AI-powered interviews."""
        logger.info('Plivo receiver started')

        self.plivo_ws = plivo_ws
        self.plivo_ws.streamId = None
        self.from_number = from_number
        self.evaluated = False
        self.call_record = None
        self.audio_interface = PlivoAudioInterface(self.plivo_ws)
        
        try:
            self.interview = await interview_service.get_interview_by_phone(f"+{from_number}")
            if not self.interview:
                logger.error(f"No interview found for phone number: +{from_number}")
                await self.text_to_speech_file(f"No interview found for your phone number", True)
                return
            
            self.questions = self.interview.questions
            questions_str = "\n".join(question for question in self.questions)
            self.interview_language = self.interview.interview_language
            self.evaluation_language = self.interview.evaluation_language
            self.criteria = self.interview.evaluation_criteria

            # Begin interview process
            ai_intro_message = f"Hello, welcome to your interview. I will be asking you the following questions:\n{questions_str}"
            await self.text_to_speech_file(ai_intro_message)

            if call_uuid:
                try:
                    self.call_record = call_record_service.record_call(call_uuid)
                    if not self.call_record:
                        logger.error(f"Failed to start call recording for UUID: {call_uuid}")
                    else:
                        logger.info(f"Call recording started for UUID: {call_uuid}")
                except Exception as e:
                    logger.error(f"Error starting call recording: {e}")
                    self.call_record = None

            while True:
                try:
                    data = await self.plivo_ws.receive_json()
                    if data['event'] == 'start':
                        self.plivo_ws.streamId = data["start"]["streamId"]
                    elif data['event'] == 'stop':
                        break

                    await self.audio_interface.handle_plivo_message(data)

                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosedError as e:
                    logger.info(f"Client connection closed: {str(e)}")
                    break
                except starlette.websockets.WebSocketDisconnect as e:
                    logger.info(f"WebSocket connection ended: {str(e)}")
                    break
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    traceback.print_exc()
                    break

        except Exception as e:
            logger.error(f"Error in plivo receiver: {e}")
            traceback.print_exc()
        finally:
            if self.call_record:
                call_record_service.stop_recording(self.call_record['call_uuid'])

            if plivo_ws.client_state != starlette.websockets.WebSocketState.DISCONNECTED:
                try:
                    await plivo_ws.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {e}")
