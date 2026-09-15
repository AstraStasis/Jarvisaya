import threading
import os
import time
from dotenv import load_dotenv
load_dotenv()

import audio_stream
from llm import JarvisRealtimeClient
from ui import run_ui, set_state, get_state
import tools
from wakeword import WakeWordDetector

class JarvisOrchestrator:
    def __init__(self):
        self.llm_thread = None
        self.llm_client = None
        
        self.wake_detector = WakeWordDetector(
            on_wake=self.wake_up,
            on_sleep=self.go_to_sleep,
            on_hide=self.hide_ui,
            on_show=self.show_ui
        )
        self.is_awake = False
        
    def start(self):
        audio_stream.start_streams()
        self.wake_detector.start()
        
        # Start offline mode first
        self.go_to_sleep()
        
        def sleep_poller():
            try:
                import win32api
                import win32con
            except ImportError:
                win32api = None
                
            last_f9_state = 0
            while True:
                if tools._SLEEP_FLAG:
                    tools._SLEEP_FLAG = False
                    self.go_to_sleep()
                    
                if win32api:
                    f9_state = win32api.GetAsyncKeyState(win32con.VK_F9)
                    if f9_state & 0x8000 and not last_f9_state & 0x8000:
                        import audio_stream
                        audio_stream.set_group_mode(not audio_stream._group_mode)
                        print(f"\n[Hotkey] Group Mode is now {'ON' if audio_stream._group_mode else 'OFF'}")
                    last_f9_state = f9_state
                    
                time.sleep(0.1)
        threading.Thread(target=sleep_poller, daemon=True).start()

    def wake_up(self):
        if self.is_awake: return
        self.is_awake = True
        print("\n[J.A.R.V.I.S.] Waking up and connecting to OpenAI...")
        self.wake_detector.set_active_mode(True)
        set_state("booting")
        
        self.llm_client = JarvisRealtimeClient(set_state)
        self.llm_thread = threading.Thread(target=self._run_llm, daemon=True)
        self.llm_thread.start()

    def go_to_sleep(self):
        if not self.is_awake and self.llm_client is None:
            # First boot
            print("\n[J.A.R.V.I.S.] Booting in offline standby mode. Say 'Jarvis' to wake me.")
            set_state("sleep")
            self.wake_detector.set_active_mode(False)
            return
            
        if not self.is_awake: return
        
        self.is_awake = False
        print("\n[J.A.R.V.I.S.] Going offline (standby mode).")
        self.wake_detector.set_active_mode(False)
        set_state("sleep")
        
        if self.llm_client:
            self.llm_client.disconnect()
            self.llm_client = None
            
    def hide_ui(self):
        tools.minimize_window()
        
    def show_ui(self):
        pass # To be implemented if we want to restore window

    def _run_llm(self):
        import asyncio
        try:
            asyncio.run(self.llm_client.run())
        except Exception as e:
            if str(e) != "Event loop is closed":
                print(f"[Orchestrator] LLM disconnected: {e}")

def main():
    import sys
    print("="*40)
    print("Starting J.A.R.V.I.S. (GPT-Live-1 Engine + Vosk Offline)...")
    print("="*40)

    if not os.environ.get("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY is not set in your .env file.")
        print("Please create a .env file and add: OPENAI_API_KEY=your_key_here")
        sys.exit(1)

    orchestrator = JarvisOrchestrator()
    
    # Start systems on background threads
    t = threading.Thread(target=orchestrator.start, daemon=True)
    t.start()


    # Run Pygame UI on the main thread (blocking)
    try:
        run_ui()
    except KeyboardInterrupt:
        print("\n[Manual Shutdown via Keyboard]")
        audio_stream.stop_streams()
        orchestrator.wake_detector.stop()
        os._exit(0)

if __name__ == "__main__":
    main()
