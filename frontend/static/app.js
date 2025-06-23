class SpeechToSpeechClient {
    constructor() {
        this.socket = null;
        this.audioContext = null;
        this.processor = null;
        this.stream = null;
        this.isConnected = false;
        this.currentState = 'ready';

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

        this.responseAudio.addEventListener('ended', () => {
            this.setState('ready');
        });
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log(`🔗 Connecting to ${wsUrl}`);

        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log(' Connected to server');
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
            console.error(' WebSocket error:', error);
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
                this.btnText.textContent = '🗣️ Response...';
                this.updateStatus('Playing response...', 'responding');
                this.mainBtn.disabled = true;
                break;

            case 'error':
                this.btnText.textContent = '❌ Error';
                this.updateStatus(statusText || 'Something went wrong', 'error');
                this.mainBtn.disabled = false;
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

            // Start recording
            this.setState('recording');
            this.socket.send(JSON.stringify({ type: 'start_recording' }));

        } catch (error) {
            console.error('Error starting recording:', error);
            this.setState('error', 'Cannot access microphone');
        }
    }

    stopRecording() {
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
                // Already handled in setState
                break;

            case 'processing':
                this.stopRecording();
                this.setState('processing');
                break;

            case 'audio_ready':
                this.setState('responding');
                this.playAudio(message.audio_url);
                break;

            case 'error':
                this.stopRecording();
                this.setState('error', message.message);

                // Auto-reset after error
                setTimeout(() => {
                    if (this.currentState === 'error') {
                        this.setState('ready');
                    }
                }, 3000);
                break;
        }
    }

    playAudio(audioUrl) {
        console.log('🔊 Playing audio:', audioUrl);

        // Show audio player
        this.audioPlayer.style.display = 'block';

        // Load and play audio
        this.responseAudio.src = audioUrl;
        this.responseAudio.load(); // Force reload to prevent caching issues

        this.responseAudio.play().then(() => {
            console.log('✅ Audio playing');
        }).catch(error => {
            console.error('❌ Error playing audio:', error);
            this.setState('error', 'Cannot play audio response');
        });
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
