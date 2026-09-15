import sounddevice as sd
import queue
import threading
import numpy as np
import time

# OpenAI Realtime Audio Format
RATE = 24000
CHANNELS = 1
DTYPE = 'int16'
CHUNK = 2400  # 100ms chunks

# Group Mode Loopback — captures ALL output devices simultaneously
import soundcard as sc
import warnings

# Mute benign 'data discontinuity' warnings from WASAPI loopback
warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

_group_mode = False
_loopback_queue = queue.Queue(maxsize=3)  # Max 300ms latency
_loopback_threads = []
_stop_loopback = False

def _loopback_worker_for_device(device_id, device_name):
    """Records loopback audio from a single output device and pushes frames to a low-latency queue."""
    try:
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)
        mic = sc.get_microphone(device_id, include_loopback=True)
        with mic.recorder(samplerate=RATE, channels=1) as recorder:
            while not _stop_loopback:
                data = recorder.record(numframes=CHUNK)
                flat = data.flatten()
                
                # Push every frame to keep clocks synced. Drop oldest if full (sliding window).
                if _loopback_queue.full():
                    try: _loopback_queue.get_nowait()
                    except queue.Empty: pass
                _loopback_queue.put(flat)
    except Exception as e:
        print(f"[Loopback:{device_name}] Error: {e}")

# Input Stream
input_queue = queue.Queue()
_input_stream = None
_is_recording = False

# Output Stream
_output_stream = None
_audio_buffer = bytearray()
_audio_buffer_lock = threading.Lock()
_current_volume = 0
_last_playing_time = 0.0

def get_current_volume():
    return _current_volume

_group_mode = False

def set_group_mode(state: bool):
    global _group_mode
    _group_mode = state
    print(f"[Audio] Group Mode set to {_group_mode}")

def _input_callback(indata, frames, time_info, status):
    if status:
        pass
    if _is_recording:
        # Check if Jarvis is speaking
        global _last_playing_time
        is_playing = False
        with _audio_buffer_lock:
            if len(_audio_buffer) > 0:
                is_playing = True
                _last_playing_time = time.time()
                
        # Copy the microphone int16 data
        mic_data = np.frombuffer(indata, dtype=DTYPE).copy()
        
        # Mix loopback if group mode is on and Jarvis is not talking
        if _group_mode:
            if time.time() - _last_playing_time <= 0.6:
                # Jarvis is playing, or just finished (allow 600ms for audio to physically clear the speakers).
                while not _loopback_queue.empty():
                    try:
                        _loopback_queue.get_nowait()
                    except queue.Empty:
                        break
                input_queue.put(bytes(indata))
            else:
                try:
                    loopback_floats = _loopback_queue.get_nowait()
                except queue.Empty:
                    loopback_floats = np.zeros(len(mic_data), dtype=np.float32)
                
                # Normalize + boost: target RMS of 0.3 (loud but safe)
                rms = float(np.sqrt(np.mean(np.square(loopback_floats))))
                if rms > 0.0001:
                    # Boost quiet Discord voices, but cap the gain so YouTube doesn't clip
                    gain = min(0.3 / rms, 12.0)  # max 12x gain to avoid clipping loud audio
                    loopback_floats = loopback_floats * gain
                loopback_int16 = (loopback_floats * 32767.0).astype(np.int32)
                
                # Safely match lengths
                if len(loopback_int16) != len(mic_data):
                    if len(loopback_int16) > len(mic_data):
                        loopback_int16 = loopback_int16[:len(mic_data)]
                    else:
                        loopback_int16 = np.pad(loopback_int16, (0, len(mic_data) - len(loopback_int16)))
                
                # Mix and clip
                mixed = mic_data.astype(np.int32) + loopback_int16
                mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
                input_queue.put(mixed.tobytes())
        else:
            input_queue.put(bytes(indata))

def _output_callback(outdata, frames, time, status):
    global _current_volume
    if status:
        pass
    
    needed = len(outdata)
    
    with _audio_buffer_lock:
        if len(_audio_buffer) >= needed:
            data = _audio_buffer[:needed]
            del _audio_buffer[:needed]
            outdata[:] = data
        elif len(_audio_buffer) > 0:
            # Not enough for a full frame, but play what we have
            data = _audio_buffer[:]
            del _audio_buffer[:]
            outdata[:len(data)] = data
            outdata[len(data):] = b'\x00' * (needed - len(data))
        else:
            data = b''
            outdata[:] = b'\x00' * needed

    if len(data) > 0:
        pcm_array = np.frombuffer(data, dtype=DTYPE)
        if len(pcm_array) > 0:
            _current_volume = np.sqrt(np.mean(np.square(pcm_array.astype(np.float32))))
        else:
            _current_volume = 0
    else:
        _current_volume = 0

def start_streams():
    global _input_stream, _output_stream, _loopback_threads, _stop_loopback
    
    # Initialize COM for the soundcard library on this background thread (Windows only)
    import os
    if os.name == 'nt':
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)
        
    print("[Audio] Initializing 24kHz streams for OpenAI Realtime API using sounddevice...")
    
    _stop_loopback = False
    _loopback_threads = []
    all_mics = sc.all_microphones(include_loopback=True)
    
    # Prioritize Stereo Mix — it captures ALL desktop audio at full pre-compression volume
    stereo_mix = next((m for m in all_mics if 'stereo mix' in m.name.lower()), None)
    if stereo_mix:
        print(f"[Audio] Stereo Mix found! Using: {stereo_mix.name}")
        t = threading.Thread(target=_loopback_worker_for_device, args=(stereo_mix.id, stereo_mix.name), daemon=True)
        t.start()
        _loopback_threads.append(t)
    else:
        # Fallback: capture from the default output/speaker device reliably
        try:
            default_spk = sc.default_speaker()
            print(f"[Audio] Stereo Mix not found. Falling back to default speaker: {default_spk.name}")
            t = threading.Thread(target=_loopback_worker_for_device, args=(default_spk.id, default_spk.name), daemon=True)
            t.start()
            _loopback_threads.append(t)
        except Exception as e:
            print(f"[Audio] Failed to get default speaker for loopback: {e}")
    
    if not _loopback_threads:
        print("[Audio] WARNING: No loopback devices found. Group Mode will not work.")

    _input_stream = sd.RawInputStream(
        samplerate=RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=CHUNK,
        callback=_input_callback
    )
    
    _output_stream = sd.RawOutputStream(
        samplerate=RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=CHUNK,
        callback=_output_callback
    )
    
    _input_stream.start()
    _output_stream.start()

def stop_streams():
    global _is_recording, _stop_loopback
    _is_recording = False
    _stop_loopback = True
    _loopback_threads.clear()
    
    if _input_stream:
        _input_stream.stop()
        _input_stream.close()
    if _output_stream:
        _output_stream.stop()
        _output_stream.close()

def set_recording(state: bool):
    global _is_recording
    _is_recording = state
    if state:
        # Flush queue
        while not input_queue.empty():
            try:
                input_queue.get_nowait()
            except queue.Empty:
                break

def play_audio(pcm_data: bytes):
    """Queues PCM16 data to be played by the speaker, with a 2x volume boost."""
    import numpy as np
    
    # Convert bytes to int16 array, multiply by 2 (volume boost), clip to prevent distortion, convert back to bytes
    audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.int32)
    audio_array = np.clip(audio_array * 2, -32768, 32767).astype(np.int16)
    
    with _audio_buffer_lock:
        _audio_buffer.extend(audio_array.tobytes())

def interrupt_playback():
    """Immediately stops currently queued playback audio (e.g. on barge-in)."""
    with _audio_buffer_lock:
        _audio_buffer.clear()
