from stt import listen
from tts import speak, stop_speaking
from llm import generate_response, generate_streamed_response, prewarm_session
from ui import run_ui, set_state
from intent import detect_intent
from dotenv import load_dotenv
import threading

load_dotenv()

import os
import time
from datetime import datetime
from ui import get_state


def _handle_intent(intent: str, arg: str, raw_input: str, clean_input: str) -> str | None:
    """
    Dispatch an intent to the correct offline handler.
    Returns a response string, or None if the intent should fall through to the LLM.
    arg      - what's left after stripping the trigger phrase
    raw_input - original full speech (for LLM)
    Returns None to signal: let the LLM handle it.
    """
    import re as _re

    # ── Time / Date ───────────────────────────────────────────────────────
    if intent == 'get_time':
        return f"It is {datetime.now().strftime('%I:%M %p')}, sir."

    if intent == 'get_date':
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}, sir."

    # ── System ────────────────────────────────────────────────────────────
    if intent == 'diagnostics':
        import psutil
        set_state('thinking')
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        bat = psutil.sensors_battery()
        bat_str = f"{bat.percent:.0f} percent" if bat else "no battery detected"
        return f"CPU at {cpu} percent, RAM at {ram} percent, battery {bat_str}."

    if intent == 'lock_screen':
        from tools import lock_screen
        lock_screen()
        return "Locking the workstation, sir."

    if intent == 'sleep_pc':



        set_state('speaking')
        speak("Are you sure you want to put the system to sleep, sir?", wait=True)
        set_state('listening')
        confirmation = listen().lower()
        if any(word in confirmation for word in ['yes', 'yep', 'sure', 'do it', 'confirm', 'sleep']):
            from tools import sleep_pc
            set_state('speaking')
            speak("Putting the system to sleep, sir.")
            sleep_pc()
            return None
        else:
            return "Sleep cancelled, sir."

    if intent == 'restart':



        set_state('speaking')
        speak("Are you sure you want to restart the system, sir?", wait=True)
        set_state('listening')
        confirmation = listen().lower()
        if any(word in confirmation for word in ['yes', 'sure', 'do it', 'confirm', 'restart']):
            from tools import restart_pc
            set_state('speaking')
            speak("Restarting the system in five seconds, sir.")
            restart_pc()
            return None
        else:
            return "Restart cancelled, sir."

    if intent == 'jarvis_sleep':
        return '__SHUTDOWN__'  # sentinel → caller breaks loop and goes to standby

    if intent == 'shutdown_pc':



        set_state('speaking')
        speak("Are you sure you want to shut down the computer, sir?", wait=True)
        set_state('listening')
        confirmation = listen().lower()
        if any(word in confirmation for word in ['yes', 'yep', 'sure', 'do it', 'confirm']):
            from tools import shutdown_pc
            set_state('speaking')
            speak("Very well, sir. Powering down.")
            time.sleep(2)
            shutdown_pc()
            return '__SHUTDOWN__'
        else:
            return "System shutdown cancelled, sir."

    # ── Volume ────────────────────────────────────────────────────────────
    if intent == 'volume_set':
        from tools import set_system_volume
        nums = _re.findall(r'\d+', arg or clean_input)
        if nums:
            level = max(0, min(100, int(nums[0])))
            set_system_volume(level)
            return f"Volume set to {level} percent, sir."
        return "What level would you like the volume at, sir?"

    if intent == 'volume_up':
        from tools import control_media
        for _ in range(5): control_media('volumeup')
        return "Volume increased, sir."

    if intent == 'volume_down':
        from tools import control_media
        for _ in range(5): control_media('volumedown')
        return "Volume decreased, sir."

    if intent == 'volume_mute':
        from tools import control_media
        control_media('volumemute')
        return "System muted, sir."

    # ── Media ─────────────────────────────────────────────────────────────
    if intent == 'media_playpause':
        from tools import control_media
        control_media('playpause')
        return "Done, sir."

    if intent == 'media_next':
        from tools import control_media
        control_media('nexttrack')
        return "Skipping track, sir."

    if intent == 'media_prev':
        from tools import control_media
        control_media('prevtrack')
        return "Going back, sir."

    # ── Screenshot ────────────────────────────────────────────────────────
    if intent == 'screenshot':
        from tools import take_screenshot
        set_state('thinking')
        path = take_screenshot()
        if path:
            return f"Screenshot saved to your desktop as {os.path.basename(path)}, sir."
        else:
            return "I apologize sir, but I was unable to capture the screen at this time."

    # ── Web / URL ─────────────────────────────────────────────────────────
    if intent == 'web_search':
        from tools import web_search
        q = arg.strip() or clean_input
        web_search(q)
        return f"Searching for {q}, sir."

    if intent == 'open_url':
        from tools import open_url
        url = arg.strip() or clean_input
        open_url(url)
        return f"Opening {url}, sir."

    # ── Folders & Files ───────────────────────────────────────────────────
    if intent == 'open_file':
        from tools import find_and_open_file
        filename = arg.strip() or clean_input
        result = find_and_open_file(filename)
        return result

    FOLDER_INTENTS = {
        'open_folder_documents': 'documents',
        'open_folder_downloads': 'downloads',
        'open_folder_desktop':   'desktop',
        'open_folder_pictures':  'pictures',
        'open_folder_music':     'music',
        'open_folder_videos':    'videos',
    }
    if intent in FOLDER_INTENTS:
        from tools import open_folder
        folder = FOLDER_INTENTS[intent]
        open_folder(folder)
        return f"Opening your {folder}, sir."

    # ── Apps ──────────────────────────────────────────────────────────────
    if intent == 'open_app':
        from tools import open_application
        app = arg.strip() or clean_input
        open_application(app)
        return f"Opening {app}, sir."

    if intent == 'close_app':
        from tools import close_application
        app = arg.strip() or clean_input
        close_application(app)
        return f"Closing {app}, sir."

    if intent == 'close_all_windows':



        set_state('speaking')
        speak("Are you sure you want to close all open applications, sir?", wait=True)
        set_state('listening')
        confirmation = listen().lower()
        if any(word in confirmation for word in ['yes', 'yep', 'sure', 'do it', 'confirm', 'close']):
            from tools import close_all_windows
            result = close_all_windows()
            return result
        else:
            return "Action cancelled, sir."

    # ── Keyboard / Typing ─────────────────────────────────────────────────
    if intent == 'type_text':
        from tools import type_text
        type_text(arg)
        return "Typed, sir."

    if intent == 'press_key':
        from tools import press_key
        press_key(arg)
        return f"Pressed {arg}, sir."

    # ── Scroll ────────────────────────────────────────────────────────────
    if intent == 'scroll_up':
        from tools import scroll_page
        scroll_page('up')
        return "Scrolled up, sir."

    if intent == 'scroll_down':
        from tools import scroll_page
        scroll_page('down')
        return "Scrolled down, sir."

    # ── Window management ─────────────────────────────────────────────────
    if intent == 'minimize_window':
        from tools import minimize_window
        minimize_window()
        return "Window minimized, sir."

    if intent == 'maximize_window':
        from tools import maximize_window
        maximize_window()
        return "Window maximized, sir."

    if intent == 'close_tab':
        from tools import close_active_tab
        close_active_tab()
        return "Tab closed, sir."

    if intent == 'new_tab':
        from tools import open_new_tab
        open_new_tab()
        return "New tab opened, sir."

    if intent == 'switch_window':
        from tools import switch_to_window
        switch_to_window(arg)
        return f"Switching to {arg}, sir."

    # ── Click / Screen interaction ────────────────────────────────────────
    if intent == 'click_element':
        from tools import click_screen_element
        result = click_screen_element(arg)
        return f"{result}, sir." if not result.endswith('.') else result

    # ── Keyboard shortcuts ────────────────────────────────────────────────
    if intent == 'save_file':
        from tools import save_file
        save_file()
        return "File saved, sir."

    if intent == 'undo':
        from tools import undo_action
        undo_action()
        return "Undone, sir."

    if intent == 'redo':
        from tools import redo_action
        redo_action()
        return "Redone, sir."

    if intent == 'copy':
        from tools import copy_text
        copy_text()
        return "Copied, sir."

    if intent == 'paste':
        from tools import paste_text
        paste_text()
        return "Pasted, sir."

    if intent == 'select_all':
        from tools import select_all
        select_all()
        return "Selected all, sir."

    # ── File ops ──────────────────────────────────────────────────────────
    if intent == 'create_folder':
        from tools import create_folder
        name = arg.strip() or "New Folder"
        create_folder(name)
        return f"Created folder '{name}' on your desktop, sir."

    if intent == 'empty_trash':
        from tools import empty_recycle_bin
        empty_recycle_bin()
        return "Recycle bin emptied, sir."

    # ── UI ────────────────────────────────────────────────────────────────
    if intent == 'hide_ui':
        import ui
        ui.hide_ui()
        return "Going dark, sir."

    if intent == 'show_ui':
        import ui
        ui.show_ui()
        return "I am back, sir."

    # ── Document writing (API for content, offline for automation) ────────
    if intent == 'write_doc':
        set_state('thinking')
        # Figure out doc type from the original input
        doc_type = 'document'
        for dtype in ['essay', 'letter', 'report', 'note', 'email']:
            if dtype in clean_input:
                doc_type = dtype
                break
        topic = arg.strip() or clean_input
        speak(f"Writing the {doc_type} now, sir. One moment.")
        
        from llm import generate_document_content
        content = generate_document_content(
            f"Write a well-structured {doc_type} about: {topic}. "
            f"Plain text only. No markdown. Use section headings ending with a colon."
        )
        from tools import write_document
        write_document(f"{doc_type}_{topic[:30]}", content, open_after=True)
        return f"The {doc_type} is saved and opened in your Documents folder, sir."

    # Unknown intent → LLM fallback
    return None


def assistant_loop():
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
            is_shutdown    = clean_prefix in ["shut down", "shutdown", "goodbye", "exit"]

            if has_wake_word:
                clean_input = user_input_lower.replace("jarvis", "", 1).strip(" ,.?!")
            else:
                clean_input = user_input_lower.strip(" ,.?!")

            if not clean_input and not is_shutdown:
                continue

            print(f"You: {user_input}")

            # ── Detect intent ─────────────────────────────────────────────
            # Always check for offline intents first to ensure they run instantly, 
            # even if the user didn't say the wake word.
            if is_shutdown:
                intent, arg = 'shutdown', ''
            else:
                intent, arg = detect_intent(clean_input)
                print(f"[Intent] {intent or 'LLM'} | arg: '{arg}'")

            response = _handle_intent(intent, arg, user_input, clean_input)

            if response == '__SHUTDOWN__':
                break                        # re-enter sleep mode
            elif response is None and intent is not None:
                pass                         # handler already spoke (sleep/restart)
            elif response is None:
                # LLM fallback for genuine conversation
                set_state('thinking')
                
                # Check if we should attach a screenshot (vision)
                image_path = None
                if any(w in clean_input for w in ["look", "see", "read", "screen", "what's this", "what is this", "what am i"]):
                    from tools import take_screenshot
                    image_path = take_screenshot()

                generator = generate_streamed_response(user_input, image_path=image_path)
                
                set_state('speaking')
                for sentence in generator:
                    tts.speak(sentence, wait=False)
                
                # Removed _audio_queue.join() to allow continuous listening for barge-in!
            else:
                set_state('speaking')
                tts.speak(response, wait=False)

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

