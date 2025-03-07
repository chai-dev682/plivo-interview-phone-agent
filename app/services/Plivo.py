import base64
import json
import webrtcvad
import websockets
import traceback
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from app.core.config import settings
from app.services.deepgram import deepgram_client
from app.services.mysql import mysql_service

class PlivoService:
    def __init__(self):
        self.elevenlabs_client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.messages = []
    
    # Converts text to speech using ElevenLabs API and sends it via Plivo WebSocket
    async def text_to_speech_file(self, text: str, plivo_ws):
        response = self.elevenlabs_client.text_to_speech.convert(
            voice_id="XrExE9yKIg1WjnnlVkGX",  # Using a pre-made voice (Adam)
            output_format="ulaw_8000",  # 8kHz audio format
            text=text,
            model_id="eleven_turbo_v2_5",
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


    async def plivo_receiver(self, plivo_ws, sample_rate=8000, silence_threshold=0.5):
        print('Plivo receiver started')

        # Initialize voice activity detection (VAD) with sensitivity level
        vad = webrtcvad.Vad(1)  # Level 1 is least sensitive

        inbuffer = bytearray(b'')  # Buffer to hold received audio chunks
        silence_start = 0  # Track when silence begins
        chunk = None  # Audio chunk
        phone_number = None

        questions = await mysql_service.get_interview_questions_by_phone(phone_number)

        first_question = """
        Hello, thank you for calling. My name is Matilda.
        I am here to help you with your interview, and I will ask some questions.
        Let's start. Okay?
        """

        try:
            await plivo_ws.accept()  # Accept the WebSocket connection
            await self.text_to_speech_file(first_question, plivo_ws)
            
            while True:
                message = await plivo_ws.receive_json()  # Use receive_json instead of async for
                try:
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
                                    self.messages.append({"role": "user", "content": transcription})
                                    if len(questions) == 0:
                                        say_goodbye = "Thank you for your time. We will contact you soon."
                                        await self.text_to_speech_file(say_goodbye, plivo_ws)
                                    else:
                                        question = questions.pop(0)
                                        self.messages.append({"role": "assistant", "content": question})
                                        await self.text_to_speech_file(question, plivo_ws)
                            inbuffer = bytearray(b'')  # Clear buffer after processing
                            silence_start = 0  # Reset silence timer
                    else:
                        silence_start = 0  # Reset if speech is detected
                except Exception as e:
                    print(f"Error processing message: {e}")
                    traceback.print_exc()

        except websockets.exceptions.ConnectionClosedError:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error processing message: {e}")
            traceback.print_exc()
        finally:
            await plivo_ws.close()

plivo_service = PlivoService()