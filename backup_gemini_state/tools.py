import os
import subprocess
import ctypes

# ---------------------------------------------------------------------------
# App registry
# ---------------------------------------------------------------------------
WINDOWS_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "cmd.exe",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
    "wordpad": "wordpad.exe",
    "task manager": "taskmgr.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
    "settings": "ms-settings:",
    "word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "teams": "teams.exe",
    "microsoft teams": "teams.exe",
    "vlc": "vlc.exe",
    "obs": "obs64.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "code": "code.exe",
    "snipping tool": "SnippingTool.exe",
    "camera": "microsoft.windows.camera:",
    "clock": "ms-clock:",
    "photos": "ms-photos:",
    "store": "ms-windows-store:",
    "maps": "bingmaps:",
    "mail": "outlookmail:",
    "calendar": "outlookcal:",
}


def open_application(app_name: str) -> str:
    """Opens a Windows application by simulating a human typing in Windows Search."""
    import pyautogui
    import time
    
    app_name_lower = app_name.lower().strip()
    
    try:
        # Simulate pressing the Windows key
        pyautogui.press('win')
        time.sleep(0.5)  # Wait for Start Menu to open
        
        # Type the app name
        pyautogui.write(app_name_lower, interval=0.03)
        time.sleep(0.8)  # Wait for search results to populate
        
        # Press enter to open the top result
        pyautogui.press('enter')
        return f"Opened {app_name}."
    except Exception as e:
        return f"Failed to open {app_name}: {e}"


def close_application(app_name: str) -> str:
    """Gracefully closes a Windows application by matching its window title."""
    import pywinauto
    from pywinauto import Desktop
    
    app_name_lower = app_name.lower().strip()
    # Strip common conversational words
    app_name_lower = app_name_lower.replace("the ", "").replace(" app", "")
    
    # Common mappings to window titles
    TITLE_MAP = {
        "word": "Word",
        "msword": "Word",
        "ms word": "Word",
        "excel": "Excel",
        "powerpoint": "PowerPoint",
        "chrome": "Google Chrome",
        "edge": "Edge",
        "notepad": "Notepad",
        "spotify": "Spotify",
        "discord": "Discord",
        "calculator": "Calculator",
        "settings": "Settings",
        "vs code": "Visual Studio Code",
        "vscode": "Visual Studio Code"
    }
    search_target = TITLE_MAP.get(app_name_lower, app_name_lower)
    
    try:
        try:
            windows = Desktop(backend="uia").windows()
            closed_count = 0
            for w in windows:
                if w.is_visible() and w.window_text():
                    title = w.window_text().lower()
                    if search_target.lower() in title:
                        try:
                            w.close()
                            closed_count += 1
                        except Exception:
                            pass
            
            if closed_count > 0:
                return f"Closed {app_name}."
        except Exception as ui_e:
            print(f"[Close App] UI Automation failed, falling back to powershell: {ui_e}")
        
        # Fallback: PowerShell regex match on process name or title
        # Use both the search_target (like "Word") and the raw name (like "msword") to be safe
        ps_cmd = f"Get-Process | Where-Object {{ $_.ProcessName -match '{app_name_lower}' -or $_.MainWindowTitle -match '{search_target}' }} | Stop-Process -Force"
        subprocess.run(["powershell", "-Command", ps_cmd], creationflags=0x08000000, check=False)
        return f"Closed {app_name}."
        
    except Exception as e:
        return f"Failed to close {app_name}: {e}"


def find_and_open_file(filename: str) -> str:
    """Searches common user directories for the file, otherwise opens a Windows Search window."""
    import os
    import subprocess
    
    filename_lower = filename.lower().strip()
    user_profile = os.environ.get('USERPROFILE', '')
    
    search_dirs = [
        os.path.join(user_profile, 'Desktop'),
        os.path.join(user_profile, 'Documents'),
        os.path.join(user_profile, 'Downloads'),
        os.path.join(user_profile, 'Pictures')
    ]
    
    # 1. Recursive search in common folders
    for search_dir in search_dirs:
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if filename_lower in f.lower():
                    filepath = os.path.join(root, f)
                    subprocess.Popen(f'start "" "{filepath}"', shell=True)
                    return f"Found and opened {f}."
                    
    # 2. If not found, open a Windows Search window in the user profile
    subprocess.Popen(f'explorer "search-ms:query={filename}&crumb=location:{user_profile}"', shell=True)
    return f"I couldn't find the exact file, so I have opened a search window for {filename}."


# ---------------------------------------------------------------------------
# Offline PC Control Tools
# ---------------------------------------------------------------------------

def take_screenshot() -> str | None:
    """Takes a screenshot and saves it to the Desktop with a timestamp. Returns None if it fails."""
    import pyautogui
    from datetime import datetime
    import traceback
    try:
        import tempfile
        temp_dir = tempfile.gettempdir()
        filename = f"jarvis_vision_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = os.path.join(temp_dir, filename)
        img = pyautogui.screenshot()
        img.save(path)
        return path
    except Exception as e:
        print(f"[Error] Screenshot failed (screen might be locked/headless): {e}")
        traceback.print_exc()
        return None


def set_system_volume(level: int) -> str:
    """
    Sets the master system volume to a specific level (0–100).
    Uses the Windows WinMM API via ctypes — no extra packages needed.
    """
    level = max(0, min(100, level))
    vol = int(level / 100 * 0xFFFF)
    packed = vol | (vol << 16)
    ctypes.windll.winmm.waveOutSetVolume(0, packed)
    return f"Volume set to {level}%."


def lock_screen() -> str:
    """Locks the Windows workstation immediately."""
    ctypes.windll.user32.LockWorkStation()
    return "Screen locked."


def sleep_pc() -> str:
    """Puts the PC to sleep."""
    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                   creationflags=0x08000000)
    return "Going to sleep."


def restart_pc() -> str:
    """Restarts the PC."""
    subprocess.run(["shutdown", "/r", "/t", "5"], creationflags=0x08000000)
    return "Restarting in 5 seconds."


def shutdown_pc() -> str:
    """Shuts down the PC."""
    subprocess.run(["shutdown", "/s", "/t", "5"], creationflags=0x08000000)
    return "Shutting down in 5 seconds."

def close_all_windows() -> str:
    """Closes all visible desktop windows gracefully."""
    import pywinauto
    from pywinauto import Desktop
    try:
        windows = Desktop(backend="uia").windows()
        count = 0
        for w in windows:
            if w.is_visible() and w.window_text():
                title = w.window_text()
                # Skip core Windows components and Jarvis itself
                if title not in ["Program Manager", "Taskbar", "J.A.R.V.I.S."]:
                    try:
                        w.close()
                        count += 1
                    except:
                        pass
        return f"Gracefully closed {count} windows."
    except Exception as e:
        return f"Error closing windows: {e}"


def type_text(text: str) -> str:
    """Types the given text at the current cursor position."""
    import pyautogui
    pyautogui.typewrite(text, interval=0.03)
    return f"Typed: {text}"


def press_key(key: str) -> str:
    """Presses a keyboard key (e.g. 'enter', 'esc', 'ctrl+c')."""
    import pyautogui
    pyautogui.hotkey(*key.split("+"))
    return f"Pressed: {key}"


def open_folder(folder_name: str) -> str:
    """Opens a common user folder in Windows Explorer."""
    FOLDER_MAP = {
        "documents": "Documents",
        "downloads": "Downloads",
        "desktop": "Desktop",
        "pictures": "Pictures",
        "music": "Music",
        "videos": "Videos",
    }
    key = folder_name.lower().strip()
    target = FOLDER_MAP.get(key, folder_name)
    path = os.path.join(os.path.expanduser("~"), target)
    if not os.path.exists(path):
        path = folder_name  # treat as literal path
    subprocess.Popen(f'explorer "{path}"', shell=True)
    return f"Opened {folder_name}."


def open_url(url: str) -> str:
    """Opens a URL in the default web browser."""
    import webbrowser
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}."


def web_search(query: str) -> str:
    """Opens a Google search for the given query."""
    import webbrowser
    encoded = query.replace(" ", "+")
    webbrowser.open(f"https://www.google.com/search?q={encoded}")
    return f"Searched for: {query}"


def write_document(filename: str, content: str, open_after: bool = True) -> str:
    """
    Creates a formatted Word (.docx) document in the user's Documents folder.
    Automatically detects headings (lines ending with ':') and body paragraphs.
    Opens the file after saving if open_after is True.
    """
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Set reasonable margins
    for section in doc.sections:
        section.top_margin    = Pt(72)
        section.bottom_margin = Pt(72)
        section.left_margin   = Pt(90)
        section.right_margin  = Pt(90)

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # Detect a heading: all-caps or ends with ':'
        if stripped.endswith(":") or stripped.isupper():
            p = doc.add_heading(stripped, level=2)
        else:
            p = doc.add_paragraph(stripped)
            p.paragraph_format.space_after = Pt(6)

    docs_folder = os.path.join(os.path.expanduser("~"), "Documents", "Jarvis")
    os.makedirs(docs_folder, exist_ok=True)

    # Sanitise filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in " _-").strip()
    path = os.path.join(docs_folder, f"{safe_name}.docx")
    doc.save(path)

    if open_after:
        subprocess.Popen(f'start "" "{path}"', shell=True)

    return path


def empty_recycle_bin() -> str:
    """Empties the Windows Recycle Bin silently."""
    try:
        import ctypes
        # SHERB_NOCONFIRMATION=1, SHERB_NOPROGRESSUI=2, SHERB_NOSOUND=4
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        return "Recycle Bin emptied."
    except Exception as e:
        return f"Could not empty Recycle Bin: {e}"


def create_folder(path: str) -> str:
    """Creates a folder at the given path (relative to Desktop if not absolute)."""
    if not os.path.isabs(path):
        path = os.path.join(os.path.expanduser("~"), "Desktop", path)
    os.makedirs(path, exist_ok=True)
    subprocess.Popen(f'explorer "{path}"', shell=True)
    return f"Created folder: {path}"


# ---------------------------------------------------------------------------
# Existing tools (kept for LLM function-calling)
# ---------------------------------------------------------------------------
import pyautogui
import psutil


def control_media(action: str) -> str:
    """
    Simulates media keys on the keyboard.
    Args:
        action: One of 'playpause', 'nexttrack', 'prevtrack', 'volumeup', 'volumedown', 'volumemute'
    """
    valid = ['playpause', 'nexttrack', 'prevtrack', 'volumeup', 'volumedown', 'volumemute']
    action = action.lower()
    if action in valid:
        try:
            pyautogui.press(action)
            return f"Executed: {action}"
        except Exception as e:
            return f"Failed: {e}"
    return f"Invalid action: {action}"


def get_system_diagnostics() -> str:
    """Fetches CPU, RAM, and battery diagnostics."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        bat = f"{battery.percent:.0f}%" if battery else "No battery (Desktop)"
        return f"CPU: {cpu}% | RAM: {ram}% | Battery: {bat}"
    except Exception as e:
        return f"Diagnostics error: {e}"


# ---------------------------------------------------------------------------
# Screen Automation — Window Management
# ---------------------------------------------------------------------------

def get_active_window() -> str:
    """Returns the title of the currently focused window."""
    import win32gui
    title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    return title or "Unknown window"


def switch_to_window(partial_title: str) -> str:
    """
    Brings a window to the foreground by partial title match.
    Use this when the user says 'switch to Chrome' or 'bring up VS Code'.
    """
    import win32gui, win32con
    target = partial_title.lower()

    def enum_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if target in title:
                results.append(hwnd)

    found = []
    win32gui.EnumWindows(enum_callback, found)
    if found:
        hwnd = found[0]
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return f"Switched to '{win32gui.GetWindowText(hwnd)}'."
    return f"No window matching '{partial_title}' found."


def _get_target_app_window():
    import win32gui, win32con
    
    def is_valid_app_window(h):
        if not win32gui.IsWindowVisible(h): return False
        title = win32gui.GetWindowText(h)
        if not title: return False
        if title in ("S.E.V.E.N.", "MSCTFIME UI", "Default IME", "Program Manager"): return False
        
        # Must not be a tool window unless it has a valid title (but we already checked title)
        # Actually, some apps use TOOLWINDOW but generally main apps don't.
        # Let's just rely on it being visible and having a title that isn't blacklisted.
        return True

    hwnd = win32gui.GetForegroundWindow()
    if not is_valid_app_window(hwnd):
        # Walk Z-order from top to find the highest valid application window
        hwnd = win32gui.GetTopWindow(None)
        while hwnd:
            if is_valid_app_window(hwnd):
                break
            hwnd = win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)
    return hwnd


def minimize_window() -> str:
    """Minimizes the currently active window."""
    import win32gui, win32con
    hwnd = _get_target_app_window()
    if hwnd:
        title = win32gui.GetWindowText(hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return f"Window '{title}' minimized."
    return "No window to minimize."


def maximize_window() -> str:
    """Maximizes (or restores) the currently active window."""
    import win32gui, win32con
    hwnd = _get_target_app_window()
    if hwnd:
        title = win32gui.GetWindowText(hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return f"Window '{title}' maximized."
    return "No window to maximize."


def scroll_page(direction: str, amount: int = 5) -> str:
    """
    Scrolls the current page up or down.
    Args:
        direction: 'up' or 'down'
        amount: number of scroll clicks (default 5)
    """
    clicks = amount if direction.lower() == 'up' else -amount
    pyautogui.scroll(clicks)
    return f"Scrolled {direction}."


# ---------------------------------------------------------------------------
# Screen Automation — UI Element Interaction (pywinauto)
# ---------------------------------------------------------------------------

def click_screen_element(element_name: str, window_title: str = '') -> str:
    """
    Finds and clicks a visible UI element (button, menu item, checkbox, link)
    by its accessible name in the currently focused window (or a named window).
    Works with Chrome, Edge, Word, Excel, File Explorer, Notepad, VS Code, etc.
    Args:
        element_name: The visible text label of the element, e.g. 'Save', 'Cancel', 'Submit'
        window_title: Optional partial title of the window to search in. Leave blank for active window.
    """
    try:
        from pywinauto import Application
        import win32gui

        if window_title:
            app = Application(backend='uia').connect(title_re=f".*{window_title}.*")
        else:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return "Could not identify the active window."
            app = Application(backend='uia').connect(title=title)

        win = app.top_window()

        # Try multiple control types so we catch buttons, links, menu items, etc.
        for ctrl_type in ['Button', 'Hyperlink', 'MenuItem', 'CheckBox', 'RadioButton', 'ListItem', None]:
            try:
                kwargs = {'title': element_name, 'found_index': 0}
                if ctrl_type:
                    kwargs['control_type'] = ctrl_type
                el = win.child_window(**kwargs)
                el.click_input()
                return f"Clicked '{element_name}'."
            except Exception:
                continue

        return f"Could not find element '{element_name}' on screen."
    except Exception as e:
        return f"Screen interaction error: {e}"


# ---------------------------------------------------------------------------
# Quick Keyboard Shortcut Helpers
# ---------------------------------------------------------------------------

def save_file() -> str:
    """Saves the current file or document (Ctrl+S)."""
    pyautogui.hotkey('ctrl', 's')
    return "File saved."

def undo_action() -> str:
    """Undoes the last action (Ctrl+Z)."""
    pyautogui.hotkey('ctrl', 'z')
    return "Undone."

def redo_action() -> str:
    """Redoes the last undone action (Ctrl+Y)."""
    pyautogui.hotkey('ctrl', 'y')
    return "Redone."

def copy_text() -> str:
    """Copies the current selection (Ctrl+C)."""
    pyautogui.hotkey('ctrl', 'c')
    return "Copied."

def paste_text() -> str:
    """Pastes from clipboard (Ctrl+V)."""
    pyautogui.hotkey('ctrl', 'v')
    return "Pasted."

def select_all() -> str:
    """Selects all content in the current field or document (Ctrl+A)."""
    pyautogui.hotkey('ctrl', 'a')
    return "Selected all."

def close_active_tab() -> str:
    """Closes the current browser/editor tab (Ctrl+W)."""
    pyautogui.hotkey('ctrl', 'w')
    return "Tab closed."

def open_new_tab() -> str:
    """Opens a new tab in the current browser or editor (Ctrl+T)."""
    pyautogui.hotkey('ctrl', 't')
    return "New tab opened."

# ---------------------------------------------------------------------------
# System and Power Commands
# ---------------------------------------------------------------------------

def get_time() -> str:
    """Returns the current local time."""
    from datetime import datetime
    return f"It is {datetime.now().strftime('%I:%M %p')}."

def get_date() -> str:
    """Returns the current date."""
    from datetime import datetime
    return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

def get_diagnostics() -> str:
    """Returns current system diagnostics including CPU, RAM, and Battery percentages."""
    import psutil
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    bat = psutil.sensors_battery()
    bat_str = f"{bat.percent:.0f} percent" if bat else "no battery detected"
    return f"CPU at {cpu} percent, RAM at {ram} percent, battery {bat_str}."

def hide_ui() -> str:
    """Hides the visual J.A.R.V.I.S. interface."""
    import ui
    ui.hide_ui()
    return "UI hidden."

def show_ui() -> str:
    """Shows the visual J.A.R.V.I.S. interface."""
    import ui
    ui.show_ui()
    return "UI shown."

_SLEEP_FLAG = False

def enter_sleep_mode() -> str:
    """
    Puts the Jarvis AI assistant into sleep/standby mode where it only listens for the wake word.
    Call this when the user says 'goodbye', 'dismissed', 'go to sleep', or indicates the conversation is over.
    """
    global _SLEEP_FLAG
    _SLEEP_FLAG = True
    return "System going to sleep."

def sleep_pc() -> str:
    """
    Puts the physical Windows computer to sleep.
    IMPORTANT: You MUST verbally ask the user for confirmation before executing this tool.
    """
    import os
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "PC is going to sleep."

def restart_pc() -> str:
    """
    Restarts the physical Windows computer.
    IMPORTANT: You MUST verbally ask the user for confirmation before executing this tool.
    """
    import os
    os.system("shutdown /r /t 5")
    return "PC is restarting."

def shutdown_pc() -> str:
    """
    Shuts down the physical Windows computer.
    IMPORTANT: You MUST verbally ask the user for confirmation before executing this tool.
    """
    import os
    os.system("shutdown /s /t 5")
    return "PC is shutting down."

def close_all_windows() -> str:
    """
    Closes all open visible windows on the screen.
    IMPORTANT: You MUST verbally ask the user for confirmation before executing this tool.
    """
    import pyautogui
    # Send Win+D to show desktop (minimizes all)
    pyautogui.hotkey('win', 'd')
    return "All windows minimized/closed."

