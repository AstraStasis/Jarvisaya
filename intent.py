"""
intent.py - Natural language intent detector for Jarvis voice commands.

Tiered matching:
  1. Direct substring match on synonym bank phrases (fast, zero overhead)
  2. RapidFuzz partial_ratio fuzzy match as fallback (>=80% confidence)
  3. Returns (None, original_text) -> LLM fallback

Usage:
    from intent import detect_intent
    intent, arg = detect_intent("hey can you snap my screen real quick")
    # -> ("screenshot", "")
"""

from rapidfuzz import fuzz

INTENT_PHRASES = {
    'get_time': [
        'what time is it', 'what is the time', 'current time', 'tell me the time',
        'what time', "what's the time", 'time is it', 'time right now',
    ],
    'get_date': [
        "what day is it", "what's today", "what is today", 'current date',
        'todays date', "what date is it", "what's the date", 'what day',
        'day is it', 'date today', "today's date",
    ],
    'diagnostics': [
        'system status', 'system diagnostics', 'cpu usage', 'ram usage',
        'memory usage', 'battery level', 'battery status', 'how is the system',
        'system performance', 'check system', 'pc health', 'pc status',
    ],
    'lock_screen': [
        'lock the screen', 'lock my screen', 'lock screen', 'lock my pc',
        'lock the computer', 'lock my computer', 'lock workstation',
        'lock the workstation', 'lock the pc',
    ],
    'sleep_pc': [
        'put the computer to sleep', 'put my computer to sleep',
        'put the pc to sleep', 'put my pc to sleep',
        'suspend the computer', 'suspend the pc',
    ],
    'restart': [
        'restart the computer', 'restart my computer', 'restart the pc',
        'reboot the computer', 'restart system', 'reboot', 'restart my pc', 'reboot pc',
    ],
    'jarvis_sleep': [
        'go to sleep', 'sleep mode', 'standby', 'dismissed', 'goodbye', 'exit',
        'shut down', 'shutdown', 'power down',
    ],
    'volume_up': [
        'turn up the volume', 'volume up', 'increase the volume',
        'make it louder', 'raise the volume', 'louder please', 'louder',
        'turn it up', 'higher volume',
    ],
    'volume_down': [
        'turn down the volume', 'volume down', 'decrease the volume',
        'make it quieter', 'lower the volume', 'quieter please', 'quieter',
        'turn it down', 'lower volume',
    ],
    'volume_mute': [
        'mute the volume', 'mute audio', 'mute the sound', 'mute',
        'silence', 'turn off the sound', 'no sound',
    ],
    'volume_set': [
        'set the volume to', 'set volume to', 'volume to', 'volume at',
        'change volume to', 'put the volume at',
    ],
    'media_playpause': [
        'pause the music', 'pause music', 'play the music', 'play music',
        'resume the music', 'resume music', 'stop the music', 'stop music',
        'pause the song', 'resume the song', 'pause playback', 'unpause',
    ],
    'media_next': [
        'next song', 'next track', 'skip song', 'skip this song',
        'skip track', 'skip this track', 'next one', 'play next',
    ],
    'media_prev': [
        'previous song', 'previous track', 'last song', 'last track',
        'go back a song', 'go back a track', 'play previous',
    ],
    'screenshot': [
        'take a screenshot', 'take screenshot', 'grab a screenshot',
        'capture my screen', 'capture the screen', 'screen capture',
        'snap my screen', 'snap the screen', 'screenshot please',
        'take a photo of my screen', 'take a picture of my screen',
        'screen grab', 'print screen',
    ],
    'web_search': [
        'search the web for', 'search online for', 'google search for',
        'search for', 'look up', 'look it up', 'google',
        'find online', 'search the internet for',
    ],
    'open_url': [
        'go to website', 'open the website', 'navigate to', 'open url',
        'go to', 'visit', 'open the site',
    ],
    'open_folder_documents': ['open my documents', 'open documents', 'show documents', 'go to documents'],
    'open_folder_downloads': ['open my downloads', 'open downloads', 'show downloads', 'go to downloads'],
    'open_folder_desktop':   ['open my desktop', 'open desktop', 'show desktop', 'go to desktop'],
    'open_folder_pictures':  ['open my pictures', 'open pictures', 'show pictures', 'go to pictures'],
    'open_folder_music':     ['open my music', 'open music', 'show music', 'go to music'],
    'open_folder_videos':    ['open my videos', 'open videos', 'show videos', 'go to videos'],
    'open_file': [
        'open the file ', 'open file ', 'find the file ', 'find file ',
        'launch the file ', 'launch file '
    ],
    'open_app': ['open up ', 'open ', 'launch ', 'start up ', 'start ', 'run ', 'fire up '],
    'close_app': ['close down ', 'close out ', 'close ', 'kill ', 'terminate ', 'shut down ', 'quit '],
    'type_text': ['type out ', 'type ', 'write out ', 'input '],
    'press_key': ['keyboard shortcut ', 'hit the key ', 'press the key ', 'press '],
    'scroll_up':   ['scroll up', 'page up', 'move up the page', 'go up the page'],
    'scroll_down': ['scroll down', 'page down', 'move down the page', 'go down the page'],
    'minimize_window': [
        'minimize the window', 'minimise the window', 'minimize window',
        'minimise window', 'collapse the window', 'shrink the window',
    ],
    'maximize_window': [
        'maximize the window', 'maximise the window', 'maximize window',
        'maximise window', 'expand the window', 'fullscreen', 'full screen', 'make it full screen',
    ],
    'close_tab': ['close this tab', 'close the tab', 'close tab', 'shut this tab', 'exit this tab'],
    'new_tab':   ['open a new tab', 'new tab', 'open new tab', 'create a new tab'],
    'switch_window': ['switch to ', 'bring up ', 'focus on ', 'go to window ', 'switch window to ', 'change to '],
    'click_element': [
        'click on the button ', 'click on the ', 'click the button ',
        'click the ', 'press the button ', 'hit the button ', 'select ',
    ],
    'save_file':  ['save the file', 'save this file', 'save the document', 'save it', 'save'],
    'undo':       ['undo that', 'undo the last', 'undo'],
    'redo':       ['redo that', 'redo'],
    'copy':       ['copy that', 'copy the text', 'copy it'],
    'paste':      ['paste that', 'paste the text', 'paste it', 'paste'],
    'select_all': ['select all', 'select everything'],
    'create_folder': [
        'create a new folder called ', 'create a folder called ',
        'make a new folder called ', 'make a folder called ',
        'create a new folder named ', 'new folder called ',
        'create a folder ', 'make a folder ', 'new folder ',
    ],
    'empty_trash': [
        'empty the recycle bin', 'empty recycle bin', 'clear the recycle bin',
        'empty the trash', 'clear trash', 'delete the trash',
    ],
    'close_all_windows': [
        'close all windows', 'close everything', 'close all apps',
        'close all applications', 'clear the screen',
    ],
    'shutdown_pc': [
        'shut down the pc', 'shut down the computer', 'shut down the system',
        'turn off the pc', 'turn off the computer', 'shutdown the pc',
        'power off the system', 'power down the pc',
    ],
    'hide_ui': [
        'hide yourself', 'hide the interface', 'hide the ui',
        'hide the hologram', 'go dark', 'disappear', 'go invisible', 'minimize yourself',
    ],
    'show_ui': [
        'show yourself', 'show the interface', 'show the ui',
        'show the hologram', 'come back', 'reappear', 'appear',
    ],
    'write_doc': [
        'write me an essay about', 'write an essay about', 'write an essay on',
        'write me a letter about', 'write a letter about', 'write a letter to',
        'write me a report about', 'write a report about', 'write a report on',
        'write me a note about', 'write a note about',
        'write me an email to', 'write an email to',
        'draft an essay about', 'draft a letter to',
        'compose an email to', 'compose a letter to',
        'create a document about', 'write a document about',
    ],
}


def _strip_trigger(text: str, phrase: str) -> str:
    phrase = phrase.rstrip()
    idx = text.find(phrase)
    if idx == -1:
        return text.strip()
    return text[idx + len(phrase):].strip(' ,.?!')


def detect_intent(text: str):
    """
    Returns (intent: str | None, argument: str).
    Falls back to (None, text) when nothing matches -> caller uses LLM.
    """
    text_lower = text.lower().strip()

    # Tier 1: direct phrase match (longest-first so specific beats generic)
    for intent, phrases in INTENT_PHRASES.items():
        for phrase in sorted(phrases, key=len, reverse=True):
            p = phrase.rstrip()
            if p in text_lower:
                return intent, _strip_trigger(text_lower, p)

    # Tier 2: fuzzy match
    best_score, best_intent, best_phrase = 0, None, None
    for intent, phrases in INTENT_PHRASES.items():
        for phrase in phrases:
            score = fuzz.partial_ratio(phrase.strip(), text_lower)
            if score > best_score:
                best_score, best_intent, best_phrase = score, intent, phrase.strip()

    if best_score >= 82 and best_intent:
        return best_intent, _strip_trigger(text_lower, best_phrase or '')

    return None, text_lower
