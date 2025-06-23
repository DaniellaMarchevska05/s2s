import os
import tempfile
import soundfile as sf
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class TranscriptionService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env")
        self.client = OpenAI(api_key=api_key)

    async def transcribe(self, audio_array, sample_rate=16000):
        """Transcribe audio array using OpenAI Whisper API"""
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                sf.write(temp_file.name, audio_array, sample_rate)
                temp_file_path = temp_file.name

            # Transcribe using OpenAI Whisper
            with open(temp_file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )

            # Clean up temporary file
            os.unlink(temp_file_path)

            print(f"Transcription: {transcript}")
            return transcript

        except Exception as e:
            print(f"Transcription error: {str(e)}")
            if 'temp_file_path' in locals():
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            raise e
