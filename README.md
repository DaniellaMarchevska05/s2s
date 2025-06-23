# 🎤 Speech-to-Speech Cat Expert

An intelligent voice assistant that answers your questions about cats — in real-time and with a friendly voice. Powered by Whisper, RAG, and ElevenLabs TTS.

![Demo Screenshot](static/demo.png) <!-- Add actual screenshot later -->

---

## 📝 Description

**Speech-to-Speech Cat Expert** is an intelligent voice assistant that supports:

- 🎙️ Voice input with automatic speech end detection (VAD)
- 🤖 RAG system with a cat knowledge base
- 🗣️ Streaming TTS for fast responses (1–2 seconds to first sound)
- 🔄 Real-time communication via WebSocket
- 🧹 Auto-cleanup of temporary files

---

## 📋 System Requirements

- **Python**: 3.8 or newer
- **pipenv**: for dependency management
- **ffmpeg**: for audio processing
- **Microphone**: for voice input
- **Internet**: for API requests

### Installing `ffmpeg`

#### Windows:
# https://ffmpeg.org/download.html

## 🚀 Installation

### 1. Clone the repository
```bash
git clone https://github.com/your-username/speech-to-speech-cats.git
cd speech-to-speech-cats
```

### 2. Install dependencies
```bash
cd backend
pipenv install
```

### 3. Setup environment variables
Create a file at `backend/.env`:
```env
# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key-here

# ElevenLabs TTS
ELEVEN_API_KEY=your-elevenlabs-api-key-here
ELEVEN_VOICE_ID=your-voice-id-here
```

### 4. Get API keys
**OpenAI**:
* Sign up at OpenAI Platform
* Create an API key from the API Keys section

**ElevenLabs**:
* Sign up at ElevenLabs
* Get API key from Settings → API Keys
* Choose a voice and copy its Voice ID

### 5. Run the application
```bash
# Activate virtual environment
pipenv shell

# Start the backend server
python app.py
```

App will be available at: http://localhost:8000

## 🎯 Usage
1. 🌐 Open http://localhost:8000 in your browser
2. 🎤 Click "Ask me about cats"
3. 🗣️ Ask a question (up to 15 seconds)
4. ⏳ Wait for response (3-7 seconds)
5. 🔊 Listen to the generated audio reply

## 🐾 Example Questions
* "Why do cats purr?"
* "Can cats see in the dark?"
* "What's the best food for kittens?"
* "Tell me a fun fact about Maine Coons."
