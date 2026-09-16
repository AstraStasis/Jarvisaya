import soundcard as sc
import time
import numpy as np

def test_loopback():
    print("Testing loopback...")
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(speaker.id, include_loopback=True)
        print(f"Loopback mic: {mic.name}")
        
        with mic.recorder(samplerate=24000, channels=1) as recorder:
            for _ in range(10):
                data = recorder.record(numframes=2400)
                vol = np.sqrt(np.mean(np.square(data)))
                print(f"Recorded 2400 frames, volume: {vol:.4f}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_loopback()
