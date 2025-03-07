from deepgram import DeepgramClient
import io
import traceback
import numpy as np
import wave

from app.core.config import settings

class DeepgramService:
    def __init__(self):
        self.client = DeepgramClient(settings.deepgram_api_key)

    # Transcribes audio to text using Deepgram API
    async def transcribe_audio(self, audio_chunk, channels=1, sample_width=2, frame_rate=8000):
        try:
            # Convert audio chunk into a NumPy array
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)

            # Create an in-memory BytesIO object for WAV file format
            wav_io = io.BytesIO()

            # Write audio data as WAV format into BytesIO
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(frame_rate)
                wav_file.writeframes(audio_data.tobytes())

            # Reset the stream position of the in-memory WAV file
            wav_io.seek(0)

            # Send the audio to Deepgram for transcription
            response = self.client.listen.rest.v("1").transcribe_file({
                'buffer': wav_io,  # Audio data in bytearray format
                'mimetype': 'audio/wav'
            }, {
                'punctuate': True,  # Enables punctuation in transcription
                'detect_language': True
            })

            # Extract the transcription result from the response
            transcription = response['results']['channels'][0]['alternatives'][0]['transcript']

            if transcription != '':
                print("Transcription: ", transcription)

            return transcription
        except Exception as e:
            print("An error occurred during transcription:")
            traceback.print_exc()
            return None

deepgram_client = DeepgramService()