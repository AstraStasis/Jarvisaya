import pyautogui
import time
import os
import numpy as np

_ui_elements_cache = {}

def scan_active_ui() -> str:
    """
    Scans the currently active window and returns a numbered list of all clickable buttons, links, and text boxes.
    Always run this first before trying to click or type into something!
    """
    try:
        import uiautomation as auto
    except ImportError:
        return "Error: uiautomation library is not installed."
        
    global _ui_elements_cache
    _ui_elements_cache.clear()
    
    window = auto.GetForegroundControl()
    window_name = window.Name if window else "Unknown"
        
    result = f"Active Window: {window_name}\n\nClickable Elements:\n"
    
    clickable_types = [
        auto.ControlType.ButtonControl,
        auto.ControlType.EditControl,
        auto.ControlType.MenuItemControl,
        auto.ControlType.HyperlinkControl,
        auto.ControlType.ListItemControl,
        auto.ControlType.TabItemControl,
        auto.ControlType.DocumentControl,
        auto.ControlType.CheckBoxControl,
        auto.ControlType.ComboBoxControl
    ]
    element_id = 1
    
    try:
        start_time = time.time()
        for control, depth in auto.WalkControl(window, maxDepth=14):
            # Abort if scanning takes more than 3 seconds or we hit 80 elements (token limit safety)
            if time.time() - start_time > 3.0 or element_id > 80:
                if element_id > 80:
                    result += "\n... [TRUNCATED - Too many elements on screen. Be more specific or scroll.]\n"
                break
                
            if control.ControlType in clickable_types:
                try:
                    # Filter out off-screen or invisible elements
                    if control.IsOffscreen:
                        continue
                        
                    rect = control.BoundingRectangle
                    if rect.width() > 0 and rect.height() > 0:
                        name = control.Name or control.AutomationId or control.ClassName or "Unnamed Element"
                        if name == "Unnamed Element" and rect.width() < 5:
                            continue
                            
                        _ui_elements_cache[str(element_id)] = {"type": "uia", "control": control}
                        control_type_name = control.ControlTypeName
                        result += f"[ID: {element_id}] '{name}' ({control_type_name})\n"
                        element_id += 1
                except Exception:
                    pass
    except Exception as e:
        return f"Error scanning UI: {str(e)}"
                
    if element_id > 1:
        return result
        
    # --- VISUAL OCR FALLBACK ---
    result = f"Active Window: {window_name}\n(UIA failed, using Visual OCR Fallback)\n\nVisible Text Elements:\n"
    try:
        import easyocr
        import cv2
        
        # Load reader (this might take a second, so we cache it globally if possible)
        # For simplicity in this script, we initialize here.
        reader = easyocr.Reader(['en'], gpu=False) # Fallback to CPU to avoid CUDA init hangs if not configured perfectly
        
        # Take screenshot
        img = pyautogui.screenshot()
        img_np = np.array(img)
        
        # Read text
        ocr_results = reader.readtext(img_np)
        
        for bbox, text, prob in ocr_results:
            if prob > 0.4 and len(text.strip()) > 0:
                # bbox is [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                x_center = int((bbox[0][0] + bbox[2][0]) / 2)
                y_center = int((bbox[0][1] + bbox[2][1]) / 2)
                
                _ui_elements_cache[str(element_id)] = {
                    "type": "coord", 
                    "x": x_center, 
                    "y": y_center, 
                    "text": text
                }
                result += f"[ID: {element_id}] '{text}'\n"
                element_id += 1
                
        if element_id == 1:
            return f"Active Window: {window_name}\nNo standard UI elements or text found on screen."
            
        return result
        
    except ImportError:
        return f"Active Window: {window_name}\nNo standard UI elements found, and 'easyocr' is not installed for the visual fallback."
    except Exception as e:
        return f"Active Window: {window_name}\nUIA failed, and OCR visual fallback encountered an error: {e}"

def click_element(element_id: str) -> str:
    """
    Clicks an element on the screen by its ID (obtained from scan_active_ui).
    """
    global _ui_elements_cache
    if element_id not in _ui_elements_cache:
        return f"Error: Element ID {element_id} not found. Please run scan_active_ui() first to get valid IDs."
        
    data = _ui_elements_cache[element_id]
    try:
        if data["type"] == "uia":
            control = data["control"]
            control.Click(simulateMove=True)
            return f"Clicked '{control.Name}' successfully."
        else:
            x, y = data["x"], data["y"]
            pyautogui.moveTo(x, y, duration=0.2)
            time.sleep(0.1)
            pyautogui.click()
            return f"Clicked visually on '{data['text']}' successfully."
    except Exception as e:
        return f"Failed to click element: {e}"

def type_into_element(element_id: str, text: str, submit: bool = True) -> str:
    """
    Clicks a text box by its ID and types the specified text into it.
    Args:
        element_id: The ID of the text box (obtained from scan_active_ui)
        text: The text to type
        submit: If true, presses Enter after typing.
    """
    global _ui_elements_cache
    if element_id not in _ui_elements_cache:
        return f"Error: Element ID {element_id} not found. Please run scan_active_ui() first to get valid IDs."
        
    data = _ui_elements_cache[element_id]
    try:
        if data["type"] == "uia":
            control = data["control"]
            control.Click(simulateMove=True)
            target_name = control.Name
        else:
            x, y = data["x"], data["y"]
            pyautogui.moveTo(x, y, duration=0.2)
            time.sleep(0.1)
            pyautogui.click()
            target_name = data["text"]
            
        time.sleep(0.2)
        pyautogui.write(text, interval=0.01)
        if submit:
            time.sleep(0.1)
            pyautogui.press('enter')
        return f"Typed into '{target_name}' successfully."
    except Exception as e:
        return f"Failed to type into element: {e}"

import difflib

def _get_best_match(description: str):
    """Internal helper to scan UI and fuzzy-match the best element."""
    scan_active_ui() # populate _ui_elements_cache
    if not _ui_elements_cache:
        return None, []
        
    names = []
    id_map = {}
    for eid, data in _ui_elements_cache.items():
        if data["type"] == "uia":
            name = data["control"].Name or data["control"].AutomationId or data["control"].ClassName or ""
        else:
            name = data["text"]
            
        name = str(name).strip().lower()
        if name:
            names.append(name)
            # Prioritize the first element that claims this name
            if name not in id_map:
                id_map[name] = eid
            
    desc_lower = description.strip().lower()
    
    # 1. Exact match
    if desc_lower in id_map:
        return id_map[desc_lower], names
        
    # 2. Safe Substring match
    if len(desc_lower) >= 3:
        for name, eid in id_map.items():
            if desc_lower in name: # "search" in "search box"
                return eid, names
                
    # 3. Fuzzy match with strict cutoff
    matches = difflib.get_close_matches(desc_lower, names, n=1, cutoff=0.6)
    if matches:
        return id_map[matches[0]], names
            
    return None, names

def find_and_click_element(description: str) -> str:
    """
    Instantly finds and clicks a UI element matching the description (e.g. 'search bar' or 'play button').
    Use this for fast clicking instead of scan_active_ui!
    Args:
        description: A short description or name of the button to click.
    """
    best_id, available_names = _get_best_match(description)
    if best_id:
        return click_element(best_id)
        
    return f"Error: Could not confidently find any button matching '{description}'. DO NOT GUESS OR RETRY randomly. Tell the user you cannot find it and ask for clarification."

def find_and_type_element(description: str, text: str, submit: bool = True) -> str:
    """
    Instantly finds a text box matching the description and types into it.
    Args:
        description: A short description of the text box (e.g. 'Search field').
        text: The text to type.
        submit: Whether to press Enter after typing.
    """
    best_id, available_names = _get_best_match(description)
    if best_id:
        return type_into_element(best_id, text, submit)
        
    return f"Error: Could not confidently find any text box matching '{description}'. DO NOT GUESS OR RETRY randomly. Tell the user you cannot find it and ask for clarification."
