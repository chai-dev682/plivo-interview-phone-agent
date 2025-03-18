import asyncio
import base64
import json
import websockets
import traceback
import starlette.websockets
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.chat_message_histories import ChatMessageHistory
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

# OpenAI API Credentials
OPENAI_API_KEY = settings.openai_api_key
OPENAI_REALTIME_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

async def openai_websocket_connect(url, headers):
    """Establishes a WebSocket connection to OpenAI API."""
    return await websockets.connect(url, additional_headers=headers)

class PlivoService:
    def __init__(self):
        self.messages = ChatMessageHistory()
        self.openai_ws = None  
        self.loop = asyncio.get_event_loop()
        self.current_question_index = 0  # Track interview progress
        self.conversation_active = False  # Mimics conversation.start_session/end_session
        # Variables set later during plivo_receiver:
        self.from_number = None
        self.call_record = None
        self.criteria = None
        self.evaluation_language = None
        self.interview = None
        self.questions = []  # list of interview questions
        self.interview_language = "en"  # default language code if not provided

        # Added flags to track conversation state:
        self.waiting_for_response = False  # Indicates if the AI is waiting for a candidate response
        self.current_question_answered = False  # Tracks if the current question has been adequately answered

    def start_session(self):
        """Starts the conversation session."""
        self.conversation_active = True
        logger.info("Conversation started")
        print("Conversation started")

    def end_session(self):
        """Ends the conversation session."""
        self.conversation_active = False
        logger.info("Conversation ended")
        print("Conversation ended")

    async def text_to_speech_file(self, text: str, end_call: bool = False):
        """
        Converts text to speech using OpenAI and sends it via Plivo WebSocket.
        """
        try:
            logger.info(f"🗣️ Requesting OpenAI TTS for: {text}")
            print(f"Requesting OpenAI TTS for: {text}")

            # OpenAI API call to generate speech
            tts_payload = {
                "model": "tts-1",  # Ensure you're using an OpenAI model that supports TTS
                "input": text,
                "voice": "alloy",
            }

            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }

            async with websockets.connect(OPENAI_REALTIME_WS_URL, extra_headers=headers) as ws:
                await ws.send(json.dumps(tts_payload))

                # Wait for OpenAI to respond with audio
                async for message in ws:
                    response = json.loads(message)

                    if "audio" in response:
                        openai_audio = response["audio"]

                        # Send the OpenAI-generated audio to Plivo
                        await self.plivo_ws.send_text(json.dumps({
                            "event": "playAudio",
                            "media": {
                                "contentType": "audio/x-mulaw",
                                "sampleRate": 8000,
                                "payload": openai_audio
                            }
                        }))

                        logger.info("🔊 Successfully sent OpenAI-generated speech to Plivo.")
                        print("Successfully sent OpenAI-generated speech to Plivo.")
                        break  # Stop after sending the first audio response

            if end_call:
                await asyncio.sleep(4)  # Allow time for audio to play
                if self.plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
                    await self.plivo_ws.close(code=1000)
                self.messages.clear()

        except Exception as e:
            logger.error(f"❌ Error in text-to-speech conversion: {e}")
            print(f"Error in text-to-speech conversion: {e}")

    def display_conversation(self):
        """Logs and prints the full conversation history."""
        conversation_history = format_conversation_history(self.messages)
        logger.info("Current conversation history:\n%s", conversation_history)
        print("Current conversation history:")
        print(conversation_history)

    def handle_transcript(self, transcription):
        """
        Handles incoming transcription from Plivo.
        Evaluates if the candidate has answered the question.
        """
        logger.info(f"Transcription: {transcription}")
        print(f"Transcription: {transcription}")
        self.messages.add_user_message(HumanMessage(transcription))
        self.display_conversation()  # Log and print the conversation history
        
        # If we're waiting for a response and received something substantial (more than 10 chars)
        if self.waiting_for_response and len(transcription.strip()) > 10:
            self.waiting_for_response = False
            self.current_question_answered = True
            # After receiving a substantial response, queue up the next question
            self.loop.create_task(self.evaluate_response_and_continue())

    async def evaluate_response_and_continue(self):
        """Evaluates the candidate's response and decides whether to move to the next question."""
        # Wait a moment to ensure the response is complete
        await asyncio.sleep(2)
        
        # Provide feedback on the answer before moving to the next question
        feedback_message = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "temperature": 0.7,
                "instructions": "Acknowledge the candidate's response briefly. If they answered completely, move to the next question. If their answer was incomplete, ask them to elaborate further on specific points they missed."
            }
        }
        await self.openai_ws.send(json.dumps(feedback_message))
        
        # Wait for feedback to be delivered
        await asyncio.sleep(5)
        
        # If the current question was answered, move to the next question
        if self.current_question_answered:
            self.current_question_answered = False
            if self.current_question_index < len(self.questions):
                await self.ask_next_question()
            else:
                await self.end_interview()

    async def ask_next_question(self):
        """Moves to the next interview question if available, or ends the interview."""
        if not self.questions:
            await self.text_to_speech_file("No interview questions found", True)
            return

        if self.current_question_index < len(self.questions):
            next_question = self.questions[self.current_question_index]
            logger.info(f"Asking question {self.current_question_index + 1}: {next_question}")
            print(f"Asking question {self.current_question_index + 1}: {next_question}")
            self.current_question_index += 1

            question_message = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "temperature": 0.8,
                    "instructions": f"Ask this question clearly: {next_question}. After asking, wait for the candidate to answer completely."
                }
            }
            print("Question message:", question_message)
            await self.openai_ws.send(json.dumps(question_message))
            self.waiting_for_response = True
        else:
            await self.end_interview()

    async def end_interview(self):
        """Finalizes the interview, evaluates the conversation, and updates the interview status."""
        logger.info("🔹 Interview completed")
        print("Interview completed")
        
        conclusion_message = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "temperature": 0.8,
                "instructions": "Thank the candidate for their time and inform them that the interview is now complete."
            }
        }
        await self.openai_ws.send(json.dumps(conclusion_message))
        print("Sent conclusion message to OpenAI.")
        await asyncio.sleep(5)
        
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
        self.messages.clear()
        self.end_session()
        if self.plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
            await self.plivo_ws.close(code=1000)

    async def receive_from_openai(self, message):
        """Handles AI-generated responses from OpenAI."""
        try:
            response = json.loads(message)

            if response['type'] == 'response.audio.delta':
                audio_delta = {
                    "event": "playAudio",
                    "media": {
                        "contentType": "audio/x-mulaw",
                        "sampleRate": 8000,
                        "payload": response['delta']
                    }
                }
                await self.plivo_ws.send_text(json.dumps(audio_delta))
                print("Sent audio delta to Plivo.")

            elif response['type'] == 'response.text':
                # Use transcript_callback to mimic the ElevenLabs flow
                self.transcript_callback(response['text'])
                print("Processed text response from OpenAI.")

            elif response['type'] == 'response.done':
                if (
                    'response' in response and 
                    'output' in response['response'] and 
                    len(response['response']['output']) > 0
                ):
                    transcript = response["response"]["output"][0]["content"][0]["transcript"]
                    print("Transcript:", transcript)
                    # If this is the initial greeting, start the first question after a delay
                    if self.current_question_index == 0 and not self.waiting_for_response:
                        await asyncio.sleep(3)
                        await self.ask_next_question()

            elif response['type'] == 'response.end':
                logger.info("OpenAI response ended, waiting for user input")
                print("OpenAI response ended, waiting for user input")

        except Exception as e:
            logger.error(f"❌ Error in receiving from OpenAI: {e}")
            print(f"Error in receiving from OpenAI: {e}")

    async def receive_from_plivo(self):
        """Handles incoming messages from Plivo and forwards audio or transcription to OpenAI."""
        try:
            while True:
                message = await self.plivo_ws.receive_text()
                data = json.loads(message)
                if data.get('event') == 'transcription':
                    self.handle_transcript(data.get('transcription', ''))
                elif data.get('event') == 'media':
                    audio_payload = {
                        "type": "input_audio_buffer.append",
                        "audio": data['media']['payload']
                    }
                    if self.openai_ws and self.openai_ws.close_code is None:
                        await self.openai_ws.send(json.dumps(audio_payload))
                elif data.get('event') == 'start':
                    print("Received start event from Plivo.")
                elif data.get('event') == 'stop':
                    print("Received stop event from Plivo.")
                    break
        except Exception as e:
            logger.error(f"❌ Error in receiving from Plivo: {e}")
            print(f"Error in receiving from Plivo: {e}")

    def transcript_callback(self, text):
        """Wrapper to handle asynchronous agent response processing."""
        async def _handle_transcript_wrapper():
            try:
                await self.handle_agent_response(text)
            except Exception as e:
                logger.error(f"Error handling transcript: {e}")
                print(f"Error handling transcript: {e}")
                traceback.print_exc()
        self.loop.run_until_complete(_handle_transcript_wrapper())

    async def handle_agent_response(self, text):
        """Processes the AI agent response, adds it to history, and checks if the call should end."""
        logger.info(f"Agent response: {text}")
        print(f"Agent response: {text}")
        self.messages.add_ai_message(AIMessage(text))
        self.display_conversation()  # Log and print the conversation history

        if len(self.messages.messages) < 5:
            return

        call_ended = chat_service.function_call(
            call_ended_prompt.format(transcript=format_conversation_history(self.messages)),
            "call_ended"
        )
        if call_ended.get("call_ended"):
            logger.info("Call ended")
            print("Call ended")
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
            self.messages.clear()
            self.end_session()
            if self.plivo_ws.client_state == starlette.websockets.WebSocketState.CONNECTED:
                await self.plivo_ws.close(code=1000)

    # Added send_openai_session_update method to resolve AttributeError.
    async def send_openai_session_update(self):
        """Configures the OpenAI session with required parameters, including a system prompt with interview instructions."""
        system_prompt = f"You are conducting an interview in language code '{self.interview_language}'. Please ask and answer all questions in this language. "
        system_prompt += "You are a human recruiter conducting this job interview. Do not mention that you are an AI, a language model, or any kind of assistant. Never refer to yourself as an AI. "
        system_prompt += "Begin by introducing yourself as the recruiter, ask for the candidate's name, and make them feel comfortable. "
        system_prompt += "Speak naturally with pauses and conversational style. Never repeat your sentences. "
        system_prompt += "For each question, wait for the candidate to answer completely. Listen carefully to their responses. "
        system_prompt += "Before moving to the next question, acknowledge their answer and provide brief feedback when appropriate. "
        system_prompt += "If the candidate gives an incomplete answer, ask follow-up questions to get more details. "
        system_prompt += "Only move to the next question when you're satisfied with the completeness of their answer. "
        system_prompt += "Be patient and give the candidate time to think and respond. This is a conversation, not a rapid-fire quiz."
        
        if self.questions:
            system_prompt += "\nYou will be asking the following questions:\n"
            for idx, question in enumerate(self.questions, start=1):
                system_prompt += f"{idx}. {question}\n"
        else:
            system_prompt += "No interview questions are available. Please inform the candidate and end the call."

        if self.criteria:
            system_prompt += f"\nEvaluation Criteria: {self.criteria}"
        
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "temperature": 0.8,
                "voice": "alloy",
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "instructions": system_prompt
            }
        }
        await self.openai_ws.send(json.dumps(session_update))
        logger.info("🔹 Session updated with system prompt.")
        print("Session updated with system prompt.")

    async def plivo_receiver(self, plivo_ws, from_number: str, call_uuid: str = None):
        """Handles WebSocket communication between Plivo and OpenAI for real-time interviews."""
        logger.info("🔹 Plivo receiver started")
        print("Plivo receiver started")

        self.plivo_ws = plivo_ws
        self.from_number = from_number
        self.call_record = None  # Initialize call recording state
        self.audio_interface = PlivoAudioInterface(self.plivo_ws)
        self.waiting_for_response = False
        self.current_question_answered = False

        try:
            # Retrieve interview details
            self.interview = await interview_service.get_interview_by_phone(f"+{from_number}")
            if not self.interview:
                logger.error(f"No interview found for phone number: +{from_number}")
                print(f"No interview found for phone number: +{from_number}")
                await self.text_to_speech_file("No interview found for your phone number", True)
                return

            # Set up interview variables
            self.questions = self.interview.questions
            self.interview_language = self.interview.interview_language
            self.evaluation_language = self.interview.evaluation_language
            self.criteria = self.interview.evaluation_criteria

            print("questions:", self.questions)
            print("Interview language:", self.interview_language)
            print("Evaluation language:", self.evaluation_language)
            print("Criteria:", self.criteria)

            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "OpenAI-Beta": "realtime=v1"}
            self.openai_ws = await openai_websocket_connect(OPENAI_REALTIME_WS_URL, headers)

            self.start_session()

            async with self.openai_ws:
                logger.info("🔹 Connected to OpenAI Realtime API")
                print("Connected to OpenAI Realtime API")
                await self.send_openai_session_update()

                # Add initial welcome message
                welcome_message = {
                    "type": "response.create",
                    "response": {
                        "modalities": ["text", "audio"],
                        "temperature": 0.8,
                        "instructions": (
                            "Introduce yourself as a recruiter (not an AI). Use a warm, professional tone. "
                            "Ask for the candidate's name and make them feel welcome. Do not mention anything about being an assistant or AI model."
                        )
                    }
                }
                await self.openai_ws.send(json.dumps(welcome_message))
                print("Sent welcome message to OpenAI.")

                # Wait for the candidate to introduce themselves
                self.waiting_for_response = True
                await asyncio.sleep(2)
                
                # Start task to handle incoming Plivo messages
                receive_plivo_task = asyncio.create_task(self.receive_from_plivo())

                # Process messages from OpenAI
                async for message in self.openai_ws:
                    if self.openai_ws.close_code is None:
                        await self.receive_from_openai(message)

                await receive_plivo_task

        except Exception as e:
            logger.error(f"❌ Error in plivo_receiver: {e}")
            print(f"Error in plivo_receiver: {e}")
            traceback.print_exc()
        finally:
            if self.call_record:
                call_record_service.stop_recording(self.call_record['call_uuid'])
            if self.openai_ws:
                await self.openai_ws.close()
            if plivo_ws.client_state != starlette.websockets.WebSocketState.DISCONNECTED:
                await plivo_ws.close()
