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

from app.core.config import settings
from app.services.chat import chat_service
from app.services.deepgram import deepgram_client
from app.services.interview import interview_service
from app.services.evaluation import evaluation_service
from app.services.callRecord import call_record_service
from app.core.prompt_templates.say_hello import say_hello_prompt
from app.core.prompt_templates.say_goodbye import say_goodbye_prompt
from app.core.prompt_templates.lang_interview import lang_interview_prompt

class PlivoService:
    def __init__(self):
        self.elevenlabs_client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.messages = ChatMessageHistory()
    
    # Converts text to speech using ElevenLabs API and sends it via Plivo WebSocket
    async def text_to_speech_file(self, text: str, plivo_ws):
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


    async def plivo_receiver(self, plivo_ws, from_number, sample_rate=8000, silence_threshold=0.5):
        print('Plivo receiver started')

        # Initialize voice activity detection (VAD) with sensitivity level
        vad = webrtcvad.Vad(1)  # Level 1 is least sensitive

        inbuffer = bytearray(b'')  # Buffer to hold received audio chunks
        silence_start = 0  # Track when silence begins
        chunk = None  # Audio chunk
        evaluated = False

        interview = await interview_service.get_interview_by_phone(f"+{from_number}")
        questions = interview.questions
        interview_language = interview.interview_language
        evaluation_language = interview.evaluation_language
        criteria = interview.evaluation_criteria

        first_question = await chat_service.chat([SystemMessage(say_hello_prompt.format(language=interview_language))])

        try:
            call_record = call_record_service.record_call()
            await self.text_to_speech_file(first_question, plivo_ws)
            
            while True:
                try:
                    message = await plivo_ws.receive_json()
                    
                    # If 'media' event, process the audio chunk
                    if message['event'] == 'media':
                        media = message['media']
                        chunk = base64.b64decode(media['payload'])
                        inbuffer.extend(chunk)

                    # If 'stop' event, end receiving process
                    if message['event'] == 'stop':
                        break

                    if chunk is None:
                        continue

                    # Check if the chunk contains speech or silence
                    is_speech = vad.is_speech(chunk, sample_rate)

                    if not is_speech:  # Detected silence
                        silence_start += 0.2  # Increment silence duration (200ms steps)
                        if silence_start >= silence_threshold:  # If silence exceeds threshold
                            if len(inbuffer) > 2048:  # Process buffered audio if large enough
                                transcription = await deepgram_client.transcribe_audio(inbuffer)
                                if transcription != '':
                                    self.messages.add_user_message(HumanMessage(transcription))
                                    if len(questions) == 0:
                                        say_goodbye = await chat_service.chat([SystemMessage(say_goodbye_prompt.format(language=interview_language))])
                                        await self.text_to_speech_file(say_goodbye, plivo_ws)
                                        call_record_service.stop_recording(call_record['call_uuid'])
                                        if not evaluated:
                                            # evaluate interview results based on the chat history
                                            await evaluation_service.evaluate_interview(self.messages, criteria, evaluation_language, interview.interview_id, interview.job_id, from_number, call_record['url'])
                                            evaluated = True
                                    else:
                                        question = questions.pop(0)
                                        lang_interview = lang_interview_prompt.format(question=question, language=interview_language)
                                        response = await chat_service.chat([SystemMessage(lang_interview)])
                                        self.messages.add_ai_message(AIMessage(response))
                                        await self.text_to_speech_file(response, plivo_ws)
                            inbuffer = bytearray(b'')  # Clear buffer after processing
                            silence_start = 0  # Reset silence timer
                    else:
                        silence_start = 0  # Reset if speech is detected

                except websockets.exceptions.ConnectionClosedError:
                    print("WebSocket connection closed by client")
                    call_record_service.stop_recording(call_record['call_uuid'])
                    evaluated = False
                    break
                except starlette.websockets.WebSocketDisconnect:
                    print("WebSocket disconnected")
                    call_record_service.stop_recording(call_record['call_uuid'])
                    evaluated = False
                    break
                except Exception as e:
                    print(f"Error processing message: {e}")
                    call_record_service.stop_recording(call_record['call_uuid'])
                    evaluated = False
                    traceback.print_exc()
                    break

        except Exception as e:
            print(f"Error in plivo receiver: {e}")
            traceback.print_exc()
        finally:
            # Check if the connection is still open using WebSocket state
            if plivo_ws.client_state != starlette.websockets.WebSocketState.DISCONNECTED:
                try:
                    await plivo_ws.close()
                except Exception as e:
                    print(f"Error closing WebSocket: {e}")

plivo_service = PlivoService()