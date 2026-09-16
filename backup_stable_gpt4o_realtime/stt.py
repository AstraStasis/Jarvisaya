import sounddevice as sd
import soundfile as sf
import tempfile
import os
import queue
import sys
import numpy as np
# Removed dynamic DLL loading since DLLs are now natively copied to ctranslate2

# Suppress HuggingFace symlink warnings on Windows before importing faster-whisper
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from faster_whisper import WhisperModel
import tts

# Initialize Whisper model once (loads into RAM for instant transcription)
print("Loading Speech-to-Text Engine (Faster-Whisper base.en)...")
model = WhisperModel("base.en", device="cpu", compute_type="int8")

def listen(fs=44100):
    print("\n[Listening for your voice...]")
    
    q = queue.Queue()
    
    def callback(indata, frames, time, status):
        q.put(indata.copy())

    # VAD parameters
    BASE_THRESHOLD = 0.015
    LOUD_THRESHOLD = 0.08   # Higher threshold for when Jarvis is speaking through speakers
    SHORT_SPEECH_SILENCE = 2.0   # Long pause if you've only said a little — give you time to continue
    NORMAL_SILENCE = 0.8         # Snappy cutoff once you've clearly spoken a full sentence
    PRE_RECORD_TIME = 0.5
    
    # 1024 frames per chunk, ~23ms per chunk at 44100Hz
    pre_record_chunks = int(PRE_RECORD_TIME * fs / 1024)
    CHUNKS_PER_SECOND = fs / 1024
    
    ring_buffer = []
    audio_data = []
    
    recording = False
    silent_chunks = 0
    active_speech_chunks = 0  # How many chunks of actual voice we've detected
    
    # Start recording in background
    stream = sd.InputStream(samplerate=fs, channels=1, blocksize=1024, callback=callback)
    
    try:
        with stream:
            while True:
                try:
                    chunk = q.get(timeout=0.1)
                except queue.Empty:
                    continue
                    
                rms = np.sqrt(np.mean(chunk**2))
                current_threshold = LOUD_THRESHOLD if tts.is_speaking else BASE_THRESHOLD
                
                if not recording:
                    ring_buffer.append(chunk)
                    if len(ring_buffer) > pre_record_chunks:
                        ring_buffer.pop(0)
                    
                    if rms > current_threshold:
                        recording = True
                        print("[Voice detected...]")
                        audio_data.extend(ring_buffer)
                        ring_buffer = []
                else:
                    audio_data.append(chunk)
                    if rms > current_threshold:
                        silent_chunks = 0
                        active_speech_chunks += 1
                    else:
                        silent_chunks += 1
                    
                    # Dynamically pick the silence limit based on how much speech we've captured
                    speech_duration_secs = active_speech_chunks / CHUNKS_PER_SECOND
                    if speech_duration_secs < 0.5:
                        # Short speech so far — be patient
                        silence_limit = int(SHORT_SPEECH_SILENCE * CHUNKS_PER_SECOND)
                    else:
                        # Enough speech detected — use the snappy cutoff
                        silence_limit = int(NORMAL_SILENCE * CHUNKS_PER_SECOND)
                        
                    if silent_chunks > silence_limit:
                        print("[Silence detected, processing...]")
                        break
    except KeyboardInterrupt:
        return "shut down"
        
    myrecording = np.concatenate(audio_data, axis=0)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_wav = f.name
        
    sf.write(temp_wav, myrecording, fs)
    
    try:
        # vad_filter=True uses Silero VAD internally to strip out background noise hallucinations
        # initial_prompt forces the AI to expect standard English commands instead of Welsh/captions
        prompt = "Jarvis, turn on the lights. What time is it?"
        segments, info = model.transcribe(temp_wav, beam_size=5, vad_filter=True, initial_prompt=prompt)
        text = "".join([segment.text for segment in segments])
        return text.strip()
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except:
                pass

if __name__ == "__main__":
    print(listen())
