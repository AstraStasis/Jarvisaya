import sounddevice as sd
import queue
import threading
import numpy as np

# OpenAI Realtime Audio Format
RATE = 24000
CHANNELS = 1
DTYPE = 'int16'
CHUNK = 2400  # 100ms chunks

# Input Stream
input_queue = queue.Queue()
_input_stream = None
_is_recording = False

# Group Mode Loopback
import soundcard as sc
_group_mode = False
_latest_loopback_data = np.zeros(CHUNK, dtype=np.float32)
_loopback_lock = threading.Lock()
_loopback_thread = None
_stop_loopback = False

def _loopback_worker():
    global _latest_loopback_data
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(speaker.id, include_loopback=True)
        with mic.recorder(samplerate=RATE, channels=1) as recorder:
            while not _stop_loopback:
                data = recorder.record(numframes=CHUNK)
                with _loopback_lock:
                    _latest_loopback_data = data.flatten()
    except Exception as e:
        print(f"[Loopback] Error: {e}")

# Output Stream
_output_stream = None
_audio_buffer = bytearray()
_audio_buffer_lock = threading.Lock()
_current_volume = 0

def get_current_volume():
    return _current_volume

def set_group_mode(state: bool):
    global _group_mode
    _group_mode = state
    print(f"[Audio] Group Mode set to {_group_mode}")

def _input_callback(indata, frames, time, status):
    if status:
        pass
    if _is_recording:
        # Check if Jarvis is speaking
        is_playing = False
        with _audio_buffer_lock:
            if len(_audio_buffer) > 0:
                is_playing = True
                
        # Copy the microphone int16 data
        mic_data = np.frombuffer(indata, dtype=DTYPE).copy()
        
        # Mix loopback if group mode is on and Jarvis is not talking
        if _group_mode and not is_playing:
            with _loopback_lock:
                loopback_floats = _latest_loopback_data.copy()
            
            # Convert loopback float (-1.0 to 1.0) to int16
            loopback_int16 = (loopback_floats * 32767.0).astype(np.int32)
            
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
    global _input_stream, _output_stream, _loopback_thread, _stop_loopback
    print("[Audio] Initializing 24kHz streams for OpenAI Realtime API using sounddevice...")
    
    # Start loopback thread
    _stop_loopback = False
    _loopback_thread = threading.Thread(target=_loopback_worker, daemon=True)
    _loopback_thread.start()

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
    """Queues PCM16 data to be played by the speaker."""
    with _audio_buffer_lock:
        _audio_buffer.extend(pcm_data)

def interrupt_playback():
    """Immediately stops currently queued playback audio (e.g. on barge-in)."""
    with _audio_buffer_lock:
        _audio_buffer.clear()