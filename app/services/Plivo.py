import asyncio
import base64
import json
import websockets
import traceback
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs import ConversationConfig
from elevenlabs import VoiceSettings
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

elevenlabs_client = ElevenLabs(api_key=settings.elevenlabs_api_key)

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
    
    # Converts text to speech using ElevenLabs API and sends it via Plivo WebSocket
    async def text_to_speech_file(self, text: str, end_call: bool = False):
        try:
            response = elevenlabs_client.text_to_speech.convert(
                voice_id="XrExE9yKIg1WjnnlVkGX",  # Using a pre-made voice (Adam)
                output_format="ulaw_8000",  # 8kHz audio format
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=0.0,
                    similarity_boost=1.0,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )

            # Collect the audio data from the response
            output = bytearray(b'')
            for chunk in response:
                if chunk:
                    output.extend(chunk)

            # Encode the audio data in Base64 format
            encode = base64.b64encode(output).decode('utf-8')

            # Send the audio data via WebSocket to Plivo with proper message type
            await self.plivo_ws.send_text(json.dumps({
                "event": "playAudio",
                "media": {
                    "contentType": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "payload": encode
                }
            }))

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
            logger.error(f"Error in text_to_speech_file: {e}")

    def handle_transcript(self, transcription):
        """Handle incoming transcription from Deepgram"""
        print(f"Transcription: {transcription}")
        self.messages.add_user_message(HumanMessage(transcription))
    
    async def handle_agent_response(self, text):
        print(f"Agent response: {text}")
        self.messages.add_ai_message(AIMessage(text))

        # check if call ended by calling the openai function tool with the transcription
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
            self.conversation.end_session()
            try:
                if self.plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
                    await self.plivo_ws.close(code=1000)  # Normal closure
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")

    def transcript_callback(self, text):
        """Wrapper to handle async transcript callback"""
        if not hasattr(self, 'loop') or not self.loop:
            logger.error("Event loop not initialized")
            return
            
        async def _handle_transcript_wrapper():
            try:
                await self.handle_agent_response(text)
            except Exception as e:
                logger.error(f"Error handling transcript: {e}")
                traceback.print_exc()

        # Create a new event loop for this thread if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the coroutine in the event loop
        loop.run_until_complete(_handle_transcript_wrapper())
    
    # def agent_response_callback(self, text):
    #     """Wrapper to handle async agent response callback"""
    #     asyncio.create_task(self.handle_agent_response(text))

    async def plivo_receiver(self, plivo_ws, from_number: str, call_uuid: str = None):
        logger.info('Plivo receiver started')
        
        # Store instance variables for use in handle_transcript
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
            
            # Initialize interview context
            self.questions = self.interview.questions
            questions_str = "\n".join(question for question in self.questions)
            self.interview_language = self.interview.interview_language
            self.evaluation_language = self.interview.evaluation_language
            self.criteria = self.interview.evaluation_criteria

            dynamic_vars = {
                "list_of_questions": questions_str,
                "language": self.interview_language
            }
            config = ConversationConfig(
                dynamic_variables=dynamic_vars,
                extra_body={},
                conversation_config_override={}
            )

            self.conversation = Conversation(
                client=elevenlabs_client,
                agent_id="9ZwQQQTZOdL9cBSHURn0",
                config=config,
                requires_auth=True,
                audio_interface=self.audio_interface,
                callback_agent_response=self.transcript_callback,
                callback_user_transcript=lambda text: self.handle_transcript(text),
            )
            self.conversation.start_session()
            logger.info("Conversation started")

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
            # Cleanup
            if self.call_record:
                call_record_service.stop_recording(self.call_record['call_uuid'])
            
            self.conversation.end_session()
            
            if plivo_ws.client_state != starlette.websockets.WebSocketState.DISCONNECTED:
                try:
                    await plivo_ws.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {e}")
