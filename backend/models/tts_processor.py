import os
import requests
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import time

load_dotenv()


class StreamingTTSProcessor:
    def __init__(self, audio_output_dir=None):
        self.api_key = os.getenv("ELEVEN_API_KEY")
        self.voice_id = os.getenv("ELEVEN_VOICE_ID")

        if not self.api_key:
            raise EnvironmentError("ELEVEN_API_KEY is missing!")
        if not self.voice_id:
            raise EnvironmentError("ELEVEN_VOICE_ID is missing!")

        if audio_output_dir:
            self.audio_output_dir = Path(audio_output_dir)
        else:
            self.audio_output_dir = Path(__file__).parent.parent.parent / "audio_output"

        self.audio_output_dir.mkdir(exist_ok=True)

    def cleanup_all_files(self):
        try:
            deleted_count = 0
            total_size = 0

            for pattern in ["*.mp3", "*.wav", "*.m4a", "*.ogg"]:
                for file_path in self.audio_output_dir.glob(pattern):
                    try:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        total_size += file_size
                        print(f" Deleted: {file_path.name}")
                    except Exception as e:
                        print(f" Could not delete {file_path.name}: {e}")

            if deleted_count > 0:
                print(f" Cleanup complete: {deleted_count} files, {total_size / 1024 / 1024:.2f} MB freed")
            else:
                print(f" Audio folder already clean")

        except Exception as e:
            print(f" Cleanup error: {e}")


    async def stream_chunks(self, chunks, session_id, websocket_callback):
        print(f" Starting streaming TTS for {len(chunks)} chunks")

        try:
            tasks = []
            for idx, chunk in enumerate(chunks):
                if chunk.strip():
                    task = self._stream_single_chunk(chunk, idx, session_id, websocket_callback)
                    tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_chunks = sum(1 for r in results if r is True)

            await websocket_callback({
                "type": "streaming_complete",
                "total_chunks": len(chunks),
                "successful_chunks": successful_chunks
            })

            print(f" Streaming complete: {successful_chunks}/{len(chunks)} chunks")
            return successful_chunks > 0

        except Exception as e:
            print(f" Streaming TTS error: {e}")
            await websocket_callback({
                "type": "error",
                "message": "TTS streaming failed"
            })
            return False

    async def _stream_single_chunk(self, chunk, index, session_id, websocket_callback):
        try:
            start_time = time.time()
            print(f" Processing chunk {index + 1}: '{chunk[:30]}...'")

            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "text": chunk,
                    "model_id": "eleven_turbo_v2",
                    "voice_settings": {
                        "stability": 0.7,
                        "similarity_boost": 0.7,
                        "style": 0.0,
                        "use_speaker_boost": False
                    }
                },
                timeout=8
            )

            if response.status_code != 200:
                print(f" TTS failed for chunk {index}: {response.status_code}")
                return False

            if not response.content:
                print(f" Empty response for chunk {index}")
                return False

            chunk_filename = f"chunk_{session_id}_{index:03d}_{int(time.time() * 1000)}.mp3"
            chunk_path = self.audio_output_dir / chunk_filename

            with open(chunk_path, "wb") as f:
                f.write(response.content)

            if chunk_path.stat().st_size == 0:
                chunk_path.unlink()
                return False

            process_time = time.time() - start_time
            print(f" Chunk {index + 1} ready in {process_time:.2f}s ({chunk_path.stat().st_size} bytes)")

            await websocket_callback({
                "type": "audio_chunk_ready",
                "chunk_index": index,
                "chunk_url": f"/audio/{chunk_filename}",
                "chunk_text": chunk[:50] + "..." if len(chunk) > 50 else chunk,
                "process_time": round(process_time, 2)
            })

            return True

        except Exception as e:
            print(f" Error processing chunk {index}: {e}")
            return False


TTSProcessor = StreamingTTSProcessor
