import os
import json
import queue
import threading
import sounddevice as sd
from vosk import Model, KaldiRecognizer

WAKE_WORDS = ["jarvis", "wake up", "online"]
SLEEP_WORDS = ["go to sleep", "stand by", "standby"]
HIDE_WORDS = ["hide yourself", "hide ui"]
SHOW_WORDS = ["show yourself", "show ui"]

class WakeWordDetector:
    def __init__(self, model_name="vosk-model-small-en-us-0.15", on_wake=None, on_sleep=None, on_hide=None, on_show=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, model_name)
        fallback_path = os.path.join(base_dir, "model")
        
        if not os.path.exists(model_path):
            if os.path.exists(fallback_path):
                model_path = fallback_path
            else:
                raise FileNotFoundError(f"Vosk model not found at {model_path}. Run download_model.py first.")
                
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        
        self.on_wake = on_wake
        self.on_sleep = on_sleep
        self.on_hide = on_hide
        self.on_show = on_show
        
        self.is_listening = False
        self.audio_queue = queue.Queue()
        self.stream = None
        self.thread = None
        self.active_mode = False # False = checking for wake words, True = checking for sleep words

    def _audio_callback(self, indata, frames, time, status):
        if status:
            pass
        self.audio_queue.put(bytes(indata))

    def _process_loop(self):
        while self.is_listening:
            try:
                data = self.audio_queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "").lower()
                
                if text:
                    print(f"[Vosk] Heard: '{text}'")
                    
                    if not self.active_mode:
                        # Asleep mode: looking for wake words
                        if any(w in text for w in WAKE_WORDS):
                            print("[Vosk] Wake word detected!")
                            if self.on_wake:
                                self.on_wake()
                    else:
                        # Awake mode: looking for sleep words
                        if any(w in text for w in SLEEP_WORDS):
                            print("[Vosk] Sleep word detected!")
                            if self.on_sleep:
                                self.on_sleep()
                                
                    if any(w in text for w in HIDE_WORDS):
                        if self.on_hide:
                            self.on_hide()
                    elif any(w in text for w in SHOW_WORDS):
                        if self.on_show:
                            self.on_show()

    def start(self):
        self.is_listening = True
        self.stream = sd.RawInputStream(
            samplerate=16000, 
            blocksize=8000, 
            dtype='int16',
            channels=1, 
            callback=self._audio_callback
        )
        self.stream.start()
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_listening = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if self.thread:
            self.thread.join()

    def set_active_mode(self, is_active):
        """
        True: OpenAI is running, we only listen for 'sleep' commands.
        False: OpenAI is disconnected, we listen for 'wake' commands.
        """
        self.active_mode = is_active
        # Reset recognizer state
        self.recognizer = KaldiRecognizer(self.model, 16000)
