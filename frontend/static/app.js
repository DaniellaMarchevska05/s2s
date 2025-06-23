class SpeechToSpeechClient {
    constructor() {
        this.socket = null;
        this.audioContext = null;
        this.processor = null;
        this.stream = null;
        this.isConnected = false;
        this.currentState = 'ready';
        this.recordingTimeout = null;

        // Streaming audio
        this.audioQueue = [];
        this.currentAudio = null;
        this.isPlayingStream = false;
        this.expectedChunks = 0;
        this.receivedChunks = 0;

        this.initElements();
        this.connect();
    }

    initElements() {
        this.mainBtn = document.getElementById('mainBtn');
        this.btnText = this.mainBtn.querySelector('.btn-text');
        this.spinner = this.mainBtn.querySelector('.spinner');
        this.status = document.getElementById('status');
        this.audioPlayer = document.getElementById('audioPlayer');
        this.responseAudio = document.getElementById('responseAudio');

        this.mainBtn.addEventListener('click', () => this.handleMainButtonClick());
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log(`🔗 Connecting to ${wsUrl}`);

        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('✅ Connected to server');
            this.isConnected = true;
            this.setState('ready');
        };

        this.socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (e) {
                console.error('Error parsing message:', e);
            }
        };

        this.socket.onclose = () => {
            console.log('🔌 Connection closed');
            this.isConnected = false;
            this.setState('error', 'Connection lost. Please refresh the page.');
        };

        this.socket.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
            this.setState('error', 'Connection error');
        };
    }

    setState(state, statusText = null) {
        this.currentState = state;

        // Reset button
        this.mainBtn.className = `main-btn ${state}`;
        this.spinner.style.display = 'none';
        this.mainBtn.disabled = false;

        switch (state) {
            case 'ready':
                this.btnText.textContent = '🎤 Ask me about cats';
                this.updateStatus(statusText || 'Ready to chat about cats!', 'ready');
                this.isPlayingStream = false;
                this.audioQueue = [];
                break;

            case 'recording':
                this.btnText.textContent = '🎙️ Recording...';
                this.updateStatus('Listening... Speak now!', 'recording');
                this.mainBtn.disabled = true;
                break;

            case 'processing':
                this.btnText.textContent = 'Processing...';
                this.spinner.style.display = 'block';
                this.updateStatus('Processing your question...', 'processing');
                this.mainBtn.disabled = true;
                break;

            case 'responding':
                this.btnText.textContent = '🗣️ Streaming...';
                this.updateStatus('Streaming response...', 'responding');
                this.mainBtn.disabled = true;
                break;

            case 'error':
                this.btnText.textContent = '❌ Error';
                this.updateStatus(statusText || 'Something went wrong', 'error');
                this.mainBtn.disabled = false;
                this.isPlayingStream = false;
                this.audioQueue = [];
                break;
        }
    }

    updateStatus(text, className = '') {
        this.status.textContent = text;
        this.status.className = `status ${className}`;
    }

    async handleMainButtonClick() {
        if (!this.isConnected) {
            this.setState('error', 'Not connected to server');
            return;
        }

        if (this.currentState === 'ready') {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            // Get microphone access
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            // Create audio context
            this.audioContext = new AudioContext({ sampleRate: 16000 });
            const source = this.audioContext.createMediaStreamSource(this.stream);

            // Load audio processor
            await this.audioContext.audioWorklet.addModule('/static/audio-processor.js');
            this.processor = new AudioWorkletNode(this.audioContext, 'audio-processor');

            // Connect audio pipeline
            source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);

            // Handle audio chunks
            this.processor.port.onmessage = (event) => {
                if (this.currentState === 'recording' && this.socket && this.socket.readyState === WebSocket.OPEN) {
                    const audioData = event.data;
                    const base64Data = this.arrayBufferToBase64(audioData.buffer);

                    this.socket.send(JSON.stringify({
                        type: 'audio_chunk',
                        data: base64Data
                    }));
                }
            };

            // Додати тайм-аут запису (15 секунд)
            this.recordingTimeout = setTimeout(() => {
                if (this.currentState === 'recording') {
                    console.log('⏱️ Recording timeout');
                    this.socket.send(JSON.stringify({ type: 'stop_recording' }));
                }
            }, 15000);

            // Start recording
            this.setState('recording');
            this.socket.send(JSON.stringify({ type: 'start_recording' }));

        } catch (error) {
            console.error('Error starting recording:', error);
            this.setState('error', 'Cannot access microphone');
        }
    }

    stopRecording() {
        // Очистити тайм-аут
        if (this.recordingTimeout) {
            clearTimeout(this.recordingTimeout);
            this.recordingTimeout = null;
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.processor = null;
    }

    handleMessage(message) {
        console.log('📨 Received:', message.type);

        switch (message.type) {
            case 'connected':
                console.log('🔗 Connected with session:', message.session_id);
                break;

            case 'recording_started':
                break;

            case 'processing':
                this.stopRecording();
                this.setState('processing');
                break;

            case 'streaming_started':
                console.log(`🎵 Starting stream: ${message.total_chunks} chunks expected`);
                this.expectedChunks = message.total_chunks;
                this.receivedChunks = 0;
                this.audioQueue = [];
                this.setState('responding');
                break;

            case 'audio_chunk_ready':
                console.log(`🎵 Chunk ${message.chunk_index + 1} ready (${message.process_time}s)`);
                this.receivedChunks++;
                this.handleAudioChunk(message);
                break;

            case 'streaming_complete':
                console.log(`✅ Streaming complete: ${message.successful_chunks}/${message.total_chunks}`);
                this.handleStreamingComplete();
                break;

            case 'error':
                this.stopRecording();
                this.setState('error', message.message);

                setTimeout(() => {
                    if (this.currentState === 'error') {
                        this.setState('ready');
                    }
                }, 3000);
                break;
        }
    }

    handleAudioChunk(chunkMessage) {
        const audioUrl = chunkMessage.chunk_url + `?t=${Date.now()}`;

        // Додати до черги
        this.audioQueue.push({
            url: audioUrl,
            index: chunkMessage.chunk_index,
            text: chunkMessage.chunk_text
        });

        // Якщо це перший чанк - почати відтворення
        if (!this.isPlayingStream) {
            this.playNextChunk();
        }

        // Оновити статус
        this.updateStatus(
            `Playing response... (${this.receivedChunks}/${this.expectedChunks})`,
            'responding'
        );
    }

    async playNextChunk() {
        if (this.audioQueue.length === 0) {
            this.isPlayingStream = false;
            return;
        }

        this.isPlayingStream = true;
        const chunk = this.audioQueue.shift();

        console.log(`🔊 Playing chunk ${chunk.index + 1}: "${chunk.text}"`);

        try {
            // Створити новий аудіо елемент для кожного чанка
            const audio = new Audio(chunk.url);
            this.currentAudio = audio;

            // Показати audio player з першим чанком
            if (chunk.index === 0) {
                this.audioPlayer.style.display = 'block';
                this.responseAudio.src = chunk.url;
            }

            // Обробник завершення чанка
            audio.addEventListener('ended', () => {
                console.log(`✅ Chunk ${chunk.index + 1} finished`);

                // Відтворити наступний чанк
                setTimeout(() => {
                    this.playNextChunk();
                }, 100); // Мала пауза між чанками
            });

            // Обробник помилки
            audio.addEventListener('error', (e) => {
                console.error(`❌ Error playing chunk ${chunk.index + 1}:`, e);
                // Спробувати наступний чанк
                setTimeout(() => {
                    this.playNextChunk();
                }, 100);
            });

            // Почати відтворення
            await audio.play();

        } catch (error) {
            console.error(`❌ Error playing chunk ${chunk.index + 1}:`, error);
            // Спробувати наступний чанк
            setTimeout(() => {
                this.playNextChunk();
            }, 100);
        }
    }

    handleStreamingComplete() {
        // Дочекатися завершення всіх чанків у черзі
        const checkComplete = () => {
            if (this.audioQueue.length === 0 && !this.isPlayingStream) {
                console.log('🎉 All chunks played');
                this.setState('ready');
            } else {
                setTimeout(checkComplete, 500);
            }
        };

        setTimeout(checkComplete, 500);
    }

    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    new SpeechToSpeechClient();
});
