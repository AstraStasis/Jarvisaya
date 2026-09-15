from stt import listen
from tts import speak, stop_speaking
from llm import generate_response, generate_streamed_response, prewarm_session
from ui import run_ui, set_state, get_state
from dotenv import load_dotenv
import threading
import os
import time
from datetime import datetime

load_dotenv()



def assistant_loop():
    import tools
    while True:
        # --- SLEEP MODE ---
        set_state('sleep')
        print("\n[Jarvis is in Sleep Mode. Say 'Wake up Jarvis' to activate.]")
        while True:
            user_input = listen().lower().strip()
            if user_input:
                print(f"[Sleep Mode Heard]: {user_input}")
            clean_prefix = user_input.replace(",", "").replace(".", "").replace("!", "").replace("?", "")
            if "wake up" in clean_prefix or "initialize" in clean_prefix:
                break

        # --- BOOT SEQUENCE ---
        set_state('booting')
        threading.Thread(target=prewarm_session, daemon=True).start()
        time.sleep(2)

        set_state('speaking')
        speak("Systems online. Good morning, sir.")
        tools._SLEEP_FLAG = False

        last_interaction_time = 0

        # --- ACTIVE MODE ---
        from rapidfuzz import fuzz
        import tts

        while True:
            set_state('listening')
            user_input = listen()

            if user_input.strip() == "":
                continue
                
            # --- Echo Cancellation & Voice Interruption ---
            if tts.current_sentence and len(user_input) > 3:
                # Compare what we heard to what Jarvis is currently saying
                similarity = fuzz.partial_ratio(user_input.lower(), tts.current_sentence.lower())
                if similarity > 70:
                    print(f"[Echo Filter] Ignored self-echo (Similarity: {similarity}%).")
                    continue
                else:
                    if tts.is_speaking:
                        print(f"\n[Barge-in] You interrupted Jarvis! (Similarity: {similarity}%)")
                        tts.stop_speaking()
                        set_state('listening')

            user_input_lower = user_input.lower().strip()
            clean_prefix = user_input_lower.replace(",", "").replace(".", "").replace("!", "")

            has_wake_word  = clean_prefix.startswith("jarvis")

            if has_wake_word:
                clean_input = user_input_lower.replace("jarvis", "", 1).strip(" ,.?!")
            else:
                clean_input = user_input_lower.strip(" ,.?!")

            if not clean_input:
                continue

            print(f"You: {user_input}")
            
            # --- Offline Command Interception ---
            # Handle basic system states instantly without API calls
            if any(cmd in clean_input for cmd in ["sleep", "stand by", "go to sleep", "power down"]):
                print("[Offline Trigger: Sleep]")
                tts.speak("Powering down into standby mode, sir.", wait=True)
                tools._SLEEP_FLAG = True
                break
                
            if any(cmd in clean_input for cmd in ["hide ui", "hide yourself", "minimize yourself", "disappear"]):
                print("[Offline Trigger: Hide UI]")
                from ui import hide_ui
                hide_ui()
                tts.speak("Hiding my interface, sir.", wait=False)
                set_state('idle')
                continue
                
            if any(cmd in clean_input for cmd in ["show ui", "show yourself", "come back", "appear"]):
                print("[Offline Trigger: Show UI]")
                from ui import show_ui
                show_ui()
                tts.speak("I am here, sir.", wait=False)
                set_state('idle')
                continue

            set_state('thinking')
            
            # --- Latency Masking (Fillers) ---
            # If the command implies an action that requires a tool call, immediately say a filler
            # to mask the 2-3 second delay of the LLM executing the tool in the cloud.
            action_verbs = ['open', 'close', 'play', 'pause', 'stop', 'volume', 'minimize', 'maximize', 
                            'scroll', 'type', 'search', 'lock', 'sleep', 'hide', 'show', 'shut down']
            if any(clean_input.startswith(v) or f" {v} " in f" {clean_input} " for v in action_verbs):
                import random
                fillers = ["Right away, sir.", "On it.", "Processing.", "One moment, sir.", "Allow me to handle that."]
                tts.speak(random.choice(fillers), wait=False)
            
            # Check if we should attach a screenshot (vision)
            image_path = None
            if any(w in clean_input for w in ["look", "see", "read", "screen", "what's this", "what is this", "what am i"]):
                image_path = tools.take_screenshot()

            generator = generate_streamed_response(user_input, image_path=image_path)
            
            set_state('speaking')
            for sentence in generator:
                tts.speak(sentence, wait=False)
                
            # Cleanup screenshot completely (bypasses recycle bin)
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"[Cleanup] Could not delete temporary screenshot: {e}")
            
            if tools._SLEEP_FLAG:
                print("[Jarvis is powering down into sleep mode...]")
                break
                
            last_interaction_time = time.time()
            set_state('idle')



def main():
    import sys
    print("="*40)
    print("Starting J.A.R.V.I.S. Systems...")
    print("="*40)

    if not os.environ.get("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY is not set in your .env file.")
        print("Please create a .env file and add: GEMINI_API_KEY=your_key_here")
        sys.exit(1)

    # Start assistant on a background thread
    t = threading.Thread(target=assistant_loop, daemon=True)
    t.start()

    # Run Pygame UI on the main thread (blocking)
    try:
        while True:
            while get_state() == 'sleep':
                time.sleep(0.1)
            run_ui()
    except KeyboardInterrupt:
        print("\n[Manual Shutdown via Keyboard]")
        os._exit(0)

if __name__ == "__main__":
    main()

