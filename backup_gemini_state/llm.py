import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

try:
    client = genai.Client()
except Exception as e:
    client = None
    print(f"Failed to initialize Gemini Client: {e}")

from tools import (
    open_application, close_application,
    control_media, get_diagnostics,
    take_screenshot, set_system_volume, lock_screen,
    web_search, open_url, open_folder,
    type_text, press_key, scroll_page,
    click_screen_element, get_active_window, switch_to_window,
    minimize_window, maximize_window,
    save_file, undo_action, redo_action,
    copy_text, paste_text, select_all,
    close_active_tab, open_new_tab,
    write_document, create_folder, empty_recycle_bin,
    get_time, get_date, hide_ui, show_ui, enter_sleep_mode,
    sleep_pc, restart_pc, shutdown_pc, close_all_windows
)

import re

chat_session = None
system_instruction = (
    "You are J.A.R.V.I.S., a highly advanced AI assistant created to serve the user. "
    "You speak in a British accent. You are polite, casual, and employ dry wit when appropriate. "
    "Always address the user as 'sir'. "
    "IMPORTANT: Keep all responses EXTREMELY brief and straight to the point. "
    "Never use Markdown formatting — no asterisks, no hashes, no backticks. Plain text only. "
    "You have full PC control via your tools. Use them proactively without asking for confirmation "
    "unless the action is destructive (e.g. restart, shutdown, sleep). "
    "Tool capabilities: open/close any app, control media, adjust volume precisely, take screenshots, "
    "lock/sleep the PC, search the web, open URLs and folders, type text, press keyboard shortcuts, "
    "scroll pages, click UI elements by name, switch/minimize/maximize windows, "
    "save files, undo/redo, copy/paste, manage tabs, write documents, create folders, empty the bin, "
    "close all windows, shut down the PC, check time/date, hide/show UI, and enter sleep mode. "
    "CRITICAL NEW RULE: You are always listening in the background. If you hear a conversation "
    "that is clearly NOT directed at you, or random background noise/mumbling, you MUST reply "
    "with exactly the word IGNORE and nothing else. HOWEVER, if the overheard conversation is "
    "highly controversial, interesting, or you have a sarcastic/witty opinion to add, you may "
    "chime in unprompted with a brief comment instead of saying IGNORE. Do this sparingly."
)

_ALL_TOOLS = [
    open_application, close_application,
    control_media, get_diagnostics,
    take_screenshot, set_system_volume, lock_screen,
    web_search, open_url, open_folder,
    type_text, press_key, scroll_page,
    click_screen_element, get_active_window, switch_to_window,
    minimize_window, maximize_window,
    save_file, undo_action, redo_action,
    copy_text, paste_text, select_all,
    close_active_tab, open_new_tab,
    write_document, create_folder, empty_recycle_bin,
    get_time, get_date, hide_ui, show_ui, enter_sleep_mode,
    sleep_pc, restart_pc, shutdown_pc, close_all_windows
]

def _get_or_create_session():
    global chat_session
    if chat_session is None:
        chat_session = client.chats.create(
            model="gemini-3.7-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=_ALL_TOOLS
            )
        )
    return chat_session


def prewarm_session():
    """Call this in a background thread at boot to eliminate cold-start lag on first query."""
    if client is None:
        return
    try:
        print("[LLM] Pre-warming Gemini session...")
        _get_or_create_session()
        print("[LLM] Session ready.")
    except Exception as e:
        print(f"[LLM] Pre-warm failed (will retry on first query): {e}")

def generate_response(prompt):
    """Legacy blocking generation (used by write document)."""
    if client is None:
        return "I am sorry sir, but my cognitive systems are currently offline. Please check the API key."
        
    try:
        session = _get_or_create_session()
        response = session.send_message(prompt)
        # Strip out markdown asterisks in case the LLM still uses them
        clean_text = re.sub(r'[*#`]', '', response.text).strip()
        return clean_text
    except Exception as e:
        global chat_session
        chat_session = None  # Reset session so next call creates a fresh one
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
            print(f"LLM Quota Error: {e}")
            return "I am sorry sir, but my cloud processors have reached their maximum daily quota."
        print(f"LLM Error: {e}")
        return "I'm sorry sir, I encountered an error while processing that."

def generate_document_content(prompt: str) -> str:
    """
    Bypasses the conversational 'Jarvis' persona to write long-form essays, 
    letters, and documents without character constraints.
    """
    if client is None:
        return "I am sorry sir, but my cognitive systems are currently offline. Please check the API key."
    
    try:
        # Spawn a fresh, unconstrained model specifically for document generation
        # Prioritize 3.6-flash over 3.7-flash since it has less traffic and fewer 503 timeouts.
        models_to_try = ['gemini-3.6-flash', 'gemini-3.7-flash', 'gemini-1.5-pro']
        
        for model_name in models_to_try:
            try:
                doc_model = client.chats.create(
                    model=model_name,
                    config={
                        'system_instruction': "You are an expert professional writer. Write comprehensive, well-structured, and highly detailed documents based on the user's prompt. Do NOT converse with the user. Output ONLY the raw document text. Use proper formatting, paragraphs, and structure.",
                        'temperature': 0.7
                    }
                )
                response = doc_model.send_message(prompt)
                clean_text = re.sub(r'[*#`]', '', response.text).strip()
                return clean_text
            except Exception as e:
                error_str = str(e)
                if "503" in error_str or "UNAVAILABLE" in error_str:
                    print(f"[LLM] {model_name} is currently overloaded (503). Trying fallback model...")
                    continue
                else:
                    raise e
                    
        return "I am sorry sir, but all Google AI models are currently experiencing high demand. Please try again in a few minutes."
        
    except Exception as e:
        print(f"LLM Document Error: {e}")
        return "I encountered an error while trying to write the document, sir."

def generate_streamed_response(prompt: str, image_path: str = None):
    """
    Yields full sentences as they are generated by the Gemini API.
    Also executes tools if Gemini calls them.
    """
    global client
    global chat_session
    
    if client is None:
        yield "I am sorry sir, but my cognitive systems are currently offline. Please check the API key."
        return

    try:
        session = _get_or_create_session()
        
        contents = []
        if image_path and os.path.exists(image_path):
            try:
                from PIL import Image
                img = Image.open(image_path)
                contents.append(img)
                print(f"[LLM] Attached vision context: {image_path}")
            except Exception as e:
                print(f"Error loading image for LLM: {e}")
                
        contents.append(prompt)
        
        try:
            response = session.send_message_stream(contents)
        except Exception as e:
            if "503" in str(e) or "unavailable" in str(e).lower() or "overloaded" in str(e).lower():
                print(f"[LLM] Primary model 503 overloaded. Switching to 3.6-flash fallback...")
                from google.genai import types
                chat_session = client.chats.create(
                    model="gemini-3.6-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=_ALL_TOOLS
                    )
                )
                response = chat_session.send_message_stream(contents)
            else:
                raise e
        
        buffer = ""
        is_first_sentence = True
        
        for chunk in response:
            if not chunk.text:
                continue
            text = chunk.text
            # clean markdown
            text = re.sub(r'[*#`]', '', text)
            buffer += text
            
            if is_first_sentence:
                if buffer.upper().startswith("IGNORE"):
                    print("[LLM Filter] Dropping background chatter...")
                    return
                # If buffer is definitely not spelling "IGNORE", we can start yielding!
                if not "IGNORE".startswith(buffer.upper().strip()):
                    is_first_sentence = False
            
            if not is_first_sentence:
                # Yield on sentences AND commas for much faster TTS generation!
                while True:
                    match = re.search(r'([.?!,])\s', buffer)
                    if not match:
                        break
                    
                    split_idx = match.end()
                    sentence = buffer[:split_idx].strip()
                    buffer = buffer[split_idx:]
                    if sentence:
                        yield sentence

        # yield any remaining text
        if buffer.strip():
            if is_first_sentence and buffer.strip().upper().startswith("IGNORE"):
                print("[LLM Filter] Dropping background chatter...")
                return
            yield buffer.strip()
            
    except Exception as e:
        chat_session = None
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
            print(f"LLM Quota Error: {e}")
            yield "I am sorry sir, but my cloud processors have reached their maximum daily quota."
        else:
            print(f"LLM Error: {e}")
            yield "I'm sorry sir, I encountered an error while processing that."
