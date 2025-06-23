import os
import requests
import asyncio
from uuid import uuid4
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class TTSProcessor:
    def __init__(self, audio_output_dir=None):
        self.api_key = os.getenv("ELEVEN_API_KEY")
        self.voice_id = os.getenv("ELEVEN_VOICE_ID")

        if not self.api_key:
            raise EnvironmentError("ELEVEN_API_KEY is missing. Add it to .env!")
        if not self.voice_id:
            raise EnvironmentError("ELEVEN_VOICE_ID is missing. Add it to .env!")

        if audio_output_dir:
            self.audio_output_dir = Path(audio_output_dir)
        else:
            self.audio_output_dir = Path(__file__).parent.parent.parent / "audio_output"

        self.audio_output_dir.mkdir(exist_ok=True)

        print(f"TTS Audio output directory: {self.audio_output_dir}")

    async def process_chunks(self, chunks, session_id):
        """Process text chunks and return combined audio file path"""
        output_path = self.audio_output_dir / f"response_{session_id}.mp3"

        if output_path.exists():
            output_path.unlink()

        temp_files = []

        try:
            print(f"Processing {len(chunks)} chunks for TTS")

            for idx, chunk in enumerate(chunks):
                print(f"Processing chunk {idx + 1}/{len(chunks)}: {chunk[:50]}...")

                if not chunk.strip():
                    print(f"Skipping empty chunk {idx + 1}")
                    continue

                # Make TTS request
                response = requests.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
                    headers={
                        "xi-api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": chunk,
                        "model_id": "eleven_monolingual_v1",
                        "voice_settings": {
                            "stability": 0.75,
                            "similarity_boost": 0.85
                        }
                    }
                )

                if response.status_code != 200:
                    print(f"TTS API error: {response.status_code}")
                    print(f"Response: {response.text}")
                    raise Exception(f"TTS failed: {response.status_code}, {response.text}")

                # Check if response has content
                if not response.content:
                    print(f"Empty response for chunk {idx + 1}")
                    continue

                # Save temporary file with absolute path
                temp_path = self.audio_output_dir / f"temp_{uuid4().hex}.mp3"

                try:
                    with open(temp_path, "wb") as f:
                        f.write(response.content)

                    # Verify file was created and has content
                    if not temp_path.exists():
                        raise Exception(f"Failed to create temp file: {temp_path}")

                    file_size = temp_path.stat().st_size
                    if file_size == 0:
                        temp_path.unlink()
                        raise Exception(f"Temp file is empty: {temp_path}")

                    print(f"Created temp file: {temp_path} ({file_size} bytes)")
                    temp_files.append(temp_path)

                except Exception as e:
                    print(f"Error saving temp file: {e}")
                    if temp_path.exists():
                        temp_path.unlink()
                    raise e

            if not temp_files:
                raise Exception("No audio files were generated")

            # Combine audio files
            if len(temp_files) == 1:
                temp_files[0].rename(output_path)
                print(f"Single file renamed to: {output_path}")
            else:
                # Combine multiple files with ffmpeg
                await self._combine_audio_files(temp_files, output_path)

            # Verify final file
            if not output_path.exists():
                raise Exception(f"Final audio file not created: {output_path}")

            final_size = output_path.stat().st_size
            if final_size == 0:
                output_path.unlink()
                raise Exception("Final audio file is empty")

            print(f"Audio saved to: {output_path} ({final_size} bytes)")
            return str(output_path)

        except Exception as e:
            print(f" TTS Processing error: {e}")

            # Clean up temp files on error
            for temp_path in temp_files:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                        print(f" Cleaned up: {temp_path}")
                    except:
                        pass

            # Clean up output file if exists and empty
            if output_path.exists() and output_path.stat().st_size == 0:
                output_path.unlink()

            raise e

    async def _combine_audio_files(self, temp_files, output_path):
        """Combine multiple audio files using ffmpeg"""
        file_list_path = self.audio_output_dir / f"temp_files_{uuid4().hex}.txt"

        try:
            # Create file list for ffmpeg
            with open(file_list_path, "w", encoding="utf-8") as f:
                for temp_path in temp_files:
                    # Use forward slashes even on Windows for ffmpeg
                    ffmpeg_path = str(temp_path).replace("\\", "/")
                    f.write(f"file '{ffmpeg_path}'\n")

            # Combine with ffmpeg
            ffmpeg_cmd = f'ffmpeg -y -f concat -safe 0 -i "{file_list_path}" -c copy "{output_path}"'
            print(f" Running ffmpeg: {ffmpeg_cmd}")

            result = os.system(ffmpeg_cmd)

            if result != 0:
                raise Exception(f"FFmpeg failed with code: {result}")

            print(f"Files combined successfully")

        finally:
            # Clean up
            if file_list_path.exists():
                file_list_path.unlink()

            for temp_path in temp_files:
                if temp_path.exists():
                    temp_path.unlink()
