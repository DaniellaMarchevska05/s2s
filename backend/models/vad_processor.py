import numpy as np
import time


class VADProcessor:
    def __init__(self, silence_threshold=0.05, silence_duration=1.5, max_recording_time=15, sample_rate=16000):
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_recording_time = max_recording_time
        self.sample_rate = sample_rate

        self.reset()

    def process_chunk(self, audio_chunk):
        """Process audio chunk and return True if speech detected"""
        if time.time() - self.recording_start_time > self.max_recording_time:
            print(f" Recording timeout ({self.max_recording_time}s)")
            return False

        rms_amplitude = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))

        is_speech = rms_amplitude > self.silence_threshold

        if is_speech:
            self.silent_chunks = 0
            self.last_speech_time = time.time()
            self.has_speech = True
            print(f" Speech detected - RMS: {rms_amplitude:.4f}")
        else:
            self.silent_chunks += 1

        return is_speech

    def should_stop_recording(self):
        """Check if recording should stop"""
        if time.time() - self.recording_start_time > self.max_recording_time:
            return True

        if not self.has_speech:
            return False

        required_chunks = int(self.silence_duration * 4)
        return self.silent_chunks >= required_chunks

    def reset(self):
        """Reset VAD state"""
        self.silent_chunks = 0
        self.last_speech_time = time.time()
        self.has_speech = False
        self.recording_start_time = time.time()
        print(" VAD reset")
