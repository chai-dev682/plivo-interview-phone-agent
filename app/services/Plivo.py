import asyncio
import base64
import json
import webrtcvad
import websockets
import traceback
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory
import starlette.websockets
import time
import numpy as np

from app.core.config import settings
from app.core.logger import logger
from app.services.chat import chat_service
from app.services.deepgram import start_live_transcription, send_audio, close
from app.services.interview import interview_service
from app.services.evaluation import evaluation_service
from app.services.callRecord import call_record_service
from app.core.prompt_templates.say_hello import say_hello_prompt
from app.core.prompt_templates.say_goodbye import say_goodbye_prompt
from app.core.prompt_templates.lang_interview import lang_interview_prompt
from app.schemas.interview import InterviewUpdate

class PlivoService:
    def __init__(self):
        self.elevenlabs_client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.messages = ChatMessageHistory()
        self.ping_interval = 25  # seconds
    
    # Converts text to speech using ElevenLabs API and sends it via Plivo WebSocket
    async def text_to_speech_file(self, text: str, plivo_ws, end_call: bool = False):
        try:
            response = self.elevenlabs_client.text_to_speech.convert(
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
            await plivo_ws.send_text(json.dumps({
                "event": "playAudio",
                "media": {
                    "contentType": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "payload": encode
                }
            }))

            if end_call:
                await asyncio.sleep(8)  # Give time for audio to finish playing
                try:
                    if plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
                        await plivo_ws.close(code=1000)  # Normal closure
                except Exception as e:
                    logger.error(f"Error during graceful shutdown: {e}")
        except Exception as e:
            logger.error(f"Error in text_to_speech_file: {e}")

    async def keep_alive(self, plivo_ws):
        while True:
            try:
                if plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
                    await plivo_ws.send_json({"event": "ping"})
                await asyncio.sleep(self.ping_interval)
            except Exception as e:
                break

    async def handle_transcript(self, transcription):
        """Handle incoming transcription from Deepgram"""
        if not hasattr(self, 'waiting_for_response') or not self.waiting_for_response:
            return

        self.waiting_for_response = False
        self.messages.add_user_message(HumanMessage(transcription))

        if len(self.questions) == 0 and not self.evaluated:
            # Handle end of interview
            say_goodbye = await chat_service.chat([SystemMessage(say_goodbye_prompt.format(language=self.interview_language))])
            self.messages.add_ai_message(AIMessage(say_goodbye))
            
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
            
            await self.text_to_speech_file(say_goodbye, self.plivo_ws, True)
            self.evaluated = True
            
        else:
            # Handle next question
            self.questions.pop(0)
            response = await chat_service.chat(self.messages.messages)
            self.messages.add_ai_message(AIMessage(response))
            await self.text_to_speech_file(response, self.plivo_ws)
            self.waiting_for_response = True

    async def plivo_receiver(self, plivo_ws, from_number: str, call_uuid: str = None, sample_rate=8000):
        logger.info('Plivo receiver started')
        
        # Store instance variables for use in handle_transcript
        self.plivo_ws = plivo_ws
        self.from_number = from_number
        self.waiting_for_response = True
        self.evaluated = False
        self.call_record = None
        
        last_activity = time.time()
        TIMEOUT = 30  # 30 seconds timeout
        error_count = 0
        MAX_ERRORS = 3
        
        # Start keep-alive task
        keep_alive_task = asyncio.create_task(self.keep_alive(plivo_ws))
        
        try:
            self.interview = await interview_service.get_interview_by_phone(f"+{from_number}")
            if not self.interview:
                logger.error(f"No interview found for phone number: +{from_number}")
                await self.text_to_speech_file(f"No interview found for your phone number", plivo_ws, True)
                return

            # Initialize interview context
            self.questions = self.interview.questions
            questions_str = "\n".join(question for question in self.questions)
            self.interview_language = self.interview.interview_language
            self.evaluation_language = self.interview.evaluation_language
            self.criteria = self.interview.evaluation_criteria
            
            lang_interview = lang_interview_prompt.format(
                list_of_questions=questions_str, 
                language=self.interview_language
            )
            self.messages.add_messages([SystemMessage(lang_interview)])

            # Start with first question
            first_question = await chat_service.chat([SystemMessage(say_hello_prompt.format(language=self.interview_language))])
            await self.text_to_speech_file(first_question, plivo_ws)
            self.messages.add_ai_message(AIMessage(first_question))

            if call_uuid:
                try:
                    self.call_record = call_record_service.record_call(call_uuid)
                    if not self.call_record:
                        logger.error(f"Failed to start call recording for UUID: {call_uuid}")
                except Exception as e:
                    logger.error(f"Error starting call recording: {e}")
                    self.call_record = None

            # Start Deepgram live transcription
            await start_live_transcription(
                callback=self.handle_transcript,
                # options={
                #     "punctuate": True
                # }
            )

            while True:
                try:
                    if time.time() - last_activity > TIMEOUT:
                        logger.warning("Connection timed out - no activity")
                        break

                    message = await asyncio.wait_for(plivo_ws.receive_json(), timeout=5.0)
                    last_activity = time.time()
                    
                    if message['event'] == 'media':
                        audio_data = base64.b64decode(message['media']['payload'])
                        await send_audio(audio_data)
                    elif message['event'] == 'stop':
                        break

                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosedError as e:
                    logger.info(f"Client connection closed: {str(e)}")
                    break
                except starlette.websockets.WebSocketDisconnect as e:
                    logger.info(f"WebSocket connection ended: {str(e)}")
                    break
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing message: {e}")
                    traceback.print_exc()
                    
                    if error_count >= MAX_ERRORS:
                        logger.error("Too many consecutive errors, closing connection")
                        break
                    
                    if "WebSocket is not connected" in str(e):
                        break
                    
                    await asyncio.sleep(1)
                    continue

        except Exception as e:
            logger.error(f"Error in plivo receiver: {e}")
            traceback.print_exc()
        finally:
            # Cleanup
            if self.call_record and not self.evaluated:
                call_record_service.stop_recording(self.call_record['call_uuid'])
            
            await close()
            
            if plivo_ws.client_state != starlette.websockets.WebSocketState.DISCONNECTED:
                try:
                    await plivo_ws.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {e}")
            
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass

plivo_service = PlivoService()