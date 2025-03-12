from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions
import traceback

from app.core.config import settings
from app.core.logger import logger


deepgram = DeepgramClient(settings.deepgram_api_key, DeepgramClientOptions(
    options={"keepalive": "true"}
))

dg_connection = deepgram.listen.asyncwebsocket.v("1")

async def start_live_transcription(callback, options=None):
    """Start a live transcription connection"""
    try:
        global dg_connection
        if not options:
            options = LiveOptions(
                model="nova-3",
                language="en-US",
            )
        
        try:
            if dg_connection:
                await dg_connection.finish()
        except Exception:
            pass

        
        async def on_message(self, result, **kwargs):
            """Handle incoming transcripts"""
            try:
                if result.is_final:
                    text = result.channel.alternatives[0].transcript
                    if text.strip():
                        logger.info(f"Transcription received: {text}")
                        if callback:
                            await callback(text)
            except Exception as e:
                logger.error(f"Error handling transcript: {e}")

        async def on_error(self, error, **kwargs):
            """Handle any errors from the websocket connection"""
            logger.error(f"Deepgram websocket error: {error}")

        # Setup event handlers with correct signatures
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        if await dg_connection.start(options) is False:
            logger.error("Failed to start live transcription")
            raise Exception("Failed to start live transcription")
        
        logger.info("Live transcription started")
        return dg_connection

    except Exception as e:
        logger.error(f"Error starting live transcription: {e}")
        traceback.print_exc()
        raise

async def send_audio(audio_data):
    """Send audio data to the live transcription connection"""
    global dg_connection
    if dg_connection:
        try:
            await dg_connection.send(audio_data)
        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {e}")
            raise

async def close():
    """Close the live transcription connection"""
    global dg_connection
    if dg_connection:
        try:
            await dg_connection.finish()
            dg_connection = None
        except Exception as e:
            logger.error(f"Error closing Deepgram connection: {e}")