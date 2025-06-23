import asyncio
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import json
import base64
import numpy as np
from dotenv import load_dotenv
import traceback
import time

from models.vad_processor import VADProcessor
from models.transcription import TranscriptionService
from models.tts_processor import TTSProcessor
from rag.cat_bot import CatExpertChat

load_dotenv()

app = FastAPI(title="Speech-to-Speech System")

PROJECT_ROOT = Path(__file__).parent.parent
AUDIO_OUTPUT_DIR = PROJECT_ROOT / "audio_output"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

transcription_service = TranscriptionService()
tts_processor = TTSProcessor(audio_output_dir=str(AUDIO_OUTPUT_DIR))
cat_bot = CatExpertChat()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        session_id = str(uuid.uuid4())

        vad_processor = VADProcessor()

        self.active_connections[websocket] = {
            "session_id": session_id,
            "vad_processor": vad_processor,
            "audio_buffer": [],
            "is_recording": False,
            "is_connected": True,
            "connected_at": time.time()
        }

        print(f" New WebSocket connection: {session_id}")
        return session_id

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            session_id = self.active_connections[websocket]["session_id"]
            self.active_connections[websocket]["is_connected"] = False
            del self.active_connections[websocket]
            print(f" WebSocket disconnected: {session_id}")

    async def send_message(self, websocket: WebSocket, message: dict):
        try:
            session = self.active_connections.get(websocket)
            if session and session["is_connected"]:
                await websocket.send_text(json.dumps(message))
                return True
        except Exception as e:
            print(f" Error sending message: {e}")
            self.disconnect(websocket)
            return False

    def get_session(self, websocket: WebSocket):
        return self.active_connections.get(websocket)


manager = ConnectionManager()


@app.get("/")
async def get_client():
    html_file = FRONTEND_DIR / "index.html"
    if not html_file.exists():
        return {"error": f"Frontend file not found: {html_file}"}

    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = None
    try:
        session_id = await manager.connect(websocket)

        await manager.send_message(websocket, {
            "type": "connected",
            "session_id": session_id,
            "message": "Ready to record"
        })

        while True:
            session = manager.get_session(websocket)
            if not session or not session["is_connected"]:
                break

            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                print(f" Message: {message.get('type')} from {session_id}")

                await handle_message(websocket, message)

            except WebSocketDisconnect:
                print(f" WebSocket disconnect: {session_id}")
                break
            except json.JSONDecodeError as e:
                print(f" JSON decode error: {e}")
                break
            except Exception as e:
                print(f" Unexpected error: {e}")
                break

    except Exception as e:
        print(f" WebSocket endpoint error: {e}")
    finally:
        manager.disconnect(websocket)


async def handle_message(websocket: WebSocket, message: dict):
    session = manager.get_session(websocket)
    if not session or not session["is_connected"]:
        return

    message_type = message.get("type")

    if message_type == "audio_chunk":
        await handle_audio_chunk(websocket, message, session)

    elif message_type == "start_recording":
        print(f" Starting recording for session {session['session_id']}")
        session["is_recording"] = True
        session["audio_buffer"] = []
        session["vad_processor"].reset()

        await manager.send_message(websocket, {
            "type": "recording_started"
        })

    elif message_type == "stop_recording":
        print(f" Manual stop recording for session {session['session_id']}")
        session["is_recording"] = False
        await process_complete_audio(websocket, session)


async def handle_audio_chunk(websocket: WebSocket, message: dict, session: dict):
    if not session["is_recording"]:
        return

    try:
        # Decode base64 audio data
        audio_data = base64.b64decode(message["data"])
        audio_array = np.frombuffer(audio_data, dtype=np.float32)

        # Add to buffer
        session["audio_buffer"].extend(audio_array)

        # Check for silence (VAD)
        vad = session["vad_processor"]
        is_speech = vad.process_chunk(audio_array)

        if vad.should_stop_recording():
            print(f" VAD detected end of speech for {session['session_id']}")
            session["is_recording"] = False
            await process_complete_audio(websocket, session)

    except Exception as e:
        print(f" Error processing audio chunk: {e}")


async def process_complete_audio(websocket: WebSocket, session: dict):
    if not session["audio_buffer"]:
        await manager.send_message(websocket, {
            "type": "error",
            "message": "No audio detected"
        })
        return

    session_id = session["session_id"]
    print(f" Processing audio for session {session_id}")

    try:
        await manager.send_message(websocket, {
            "type": "processing"
        })

        # Convert audio buffer to numpy array
        audio_array = np.array(session["audio_buffer"], dtype=np.float32)

        # Transcribe audio
        transcription = await transcription_service.transcribe(audio_array)

        if not transcription.strip():
            await manager.send_message(websocket, {
                "type": "error",
                "message": "No speech detected"
            })
            return

        print(f" Transcription: {transcription}")

        # Get response from RAG
        rag_response = cat_bot.chat(transcription)
        chunks = rag_response["chunks"]

        if not chunks:
            await manager.send_message(websocket, {
                "type": "error",
                "message": "No response generated"
            })
            return

        print(f" Generated {len(chunks)} chunks")

        # Process TTS in chunks
        audio_file_path = await tts_processor.process_chunks(chunks, session_id)

        if not audio_file_path or not os.path.exists(audio_file_path):
            await manager.send_message(websocket, {
                "type": "error",
                "message": "Failed to generate audio"
            })
            return

        # Send audio file URL with timestamp to prevent caching
        filename = os.path.basename(audio_file_path)
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds

        await manager.send_message(websocket, {
            "type": "audio_ready",
            "audio_url": f"/audio/{filename}?t={timestamp}"
        })

        print(f" Audio ready for {session_id}: {filename}")

    except Exception as e:
        print(f" Error in process_complete_audio: {e}")
        print(traceback.format_exc())
        await manager.send_message(websocket, {
            "type": "error",
            "message": "Processing failed"
        })
    finally:
        # Reset for next question
        session["audio_buffer"] = []
        session["vad_processor"].reset()


# Serve audio files
@app.get("/audio/{filename}")
async def get_audio_file(filename: str):
    file_path = AUDIO_OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(
            str(file_path),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return {"error": "File not found"}


if __name__ == "__main__":
    import uvicorn

    print(f" Audio output: {AUDIO_OUTPUT_DIR}")

    for port in [8000, 8001, 8002, 8003]:
        try:
            print(f" Starting server on http://localhost:{port}")
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
            break
        except OSError as e:
            if "10048" in str(e):
                print(f" Port {port} is busy, trying next...")
                continue
            else:
                raise e
