import asyncio
import threading
import queue
import edge_tts
import sounddevice as sd
import miniaudio
import numpy as np
import random
import time

VOICE = "en-GB-ThomasNeural"  # Overridden by line 35 if ElevenLabs not set

_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()

# Audio playback queue and volume tracking
_audio_queue = queue.Queue()
_current_volume = 0.0
is_speaking = False
current_sentence = ""
_abort_playback = False

def get_current_volume() -> float:
    """Returns the current RMS volume of the playing audio, or 0 if silent."""
    return _current_volume

import os
import requests
import json

_elevenlabs_quota_exceeded = False

# High quality British female voice for fallback
VOICE = "en-GB-SoniaNeural"

async def _stream_audio_pcm(text: str):
    global _elevenlabs_quota_exceeded

    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")

    if api_key and voice_id and not _elevenlabs_quota_exceeded:
        # Free tier requires mp3. We use streaming MP3.
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?output_format=mp3_44100_128"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        data = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        try:
            def fetch_stream():
                # We do a blocking post here, but because we send small comma-separated text chunks, 
                # this returns instantly.
                return requests.post(url, json=data, headers=headers, timeout=10)
            
            response = await asyncio.to_thread(fetch_stream)
            
            if response.status_code == 200:
                audio_data = response.content
                if not _abort_playback and audio_data:
                    decoded = miniaudio.decode(audio_data, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1)
                    samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
                    yield samples, decoded.sample_rate
                return 
            
            elif response.status_code in [401, 402, 403, 429]:
                print(f"[ElevenLabs] Quota exceeded or unauthorized (Status {response.status_code}). Falling back to edge-tts.")
                _elevenlabs_quota_exceeded = True
            else:
                print(f"[ElevenLabs] Error {response.status_code}: {response.text}. Falling back.")
        except Exception as e:
            print(f"[ElevenLabs] Request failed: {e}. Falling back.")

    # Edge-TTS Fallback (MP3 downloading into miniaudio decoder)
    communicate = edge_tts.Communicate(text, VOICE)
    audio_data = b""
    async for chunk in communicate.stream():
        if _abort_playback:
            break
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    
    if not _abort_playback and audio_data:
        decoded = miniaudio.decode(audio_data, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1)
        samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
        yield samples, decoded.sample_rate

def _playback_worker():
    global is_speaking, _current_volume, current_sentence, _abort_playback
    while True:
        text = _audio_queue.get()
        if text is None:
            break
        
        is_speaking = True
        current_sentence = text
        _abort_playback = False
        try:
            async def process_and_play():
                global _current_volume
                stream = None
                
                async for samples, sample_rate in _stream_audio_pcm(text):
                    if _abort_playback:
                        break
                    
                    if stream is None:
                        stream = sd.OutputStream(samplerate=sample_rate, channels=1, dtype='float32')
                        stream.start()
                    
                    # Play audio in chunks and calculate RMS
                    chunk_size = 1024
                    for i in range(0, len(samples), chunk_size):
                        if _abort_playback:
                            break
                        
                        chunk = samples[i:i+chunk_size]
                        rms = np.sqrt(np.mean(chunk**2))
                        _current_volume = rms * 10000.0  # Scale up for UI
                        
                        if len(chunk) < chunk_size:
                            chunk = np.pad(chunk, (0, chunk_size - len(chunk)), 'constant')
                            
                        stream.write(chunk)
                
                if stream is not None:
                    stream.stop()
                    stream.close()
                    
            # Run the streaming task
            asyncio.run_coroutine_threadsafe(process_and_play(), _loop).result()

        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            _current_volume = 0.0
            current_sentence = ""
            # Only set speaking to false if queue is empty
            if _audio_queue.empty():
                is_speaking = False
            _audio_queue.task_done()

# Start background playback thread
threading.Thread(target=_playback_worker, daemon=True).start()

def speak(text: str, wait: bool = True):
    """
    Queues text to be spoken. If wait=True, blocks until speech completes.
    If wait=False, returns immediately (useful for streaming).
    """
    text = text.replace("J.A.R.V.I.S.", "Jarvis").replace("J.A.R.V.I.S", "Jarvis")
    if text.strip():
        print(f"\nJARVIS: {text}\n")
        _audio_queue.put(text)
        if wait:
            _audio_queue.join()

def stop_speaking():
    """Clears the queue and aborts current playback."""
    global _abort_playback
    _abort_playback = True
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
            _audio_queue.task_done()
        except queue.Empty:
            break

if __name__ == "__main__":
    speak("Systems online. All audio pathways are now fully operational, sir.", wait=True)

