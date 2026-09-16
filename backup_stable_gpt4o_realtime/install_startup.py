import os
import sys
import win32com.client

def create_startup_shortcut():
    print("Setting up J.A.R.V.I.S. Windows Startup Integration...")
    
    # Path to the current user's Startup folder
    startup_dir = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
    shortcut_path = os.path.join(startup_dir, "Jarvis.lnk")
    
    # Point strictly to the local Virtual Environment pythonw.exe
    venv_python = os.path.join(os.path.abspath("."), "venv", "Scripts", "pythonw.exe")
    if os.path.exists(venv_python):
        python_exe = venv_python
    else:
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        
    script_path = os.path.abspath("main.py")
    work_dir = os.path.abspath(".")
    
    # Create the actual Windows .lnk shortcut using pywin32
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = python_exe
    shortcut.Arguments = f'"{script_path}"'
    shortcut.WorkingDirectory = work_dir
    shortcut.IconLocation = python_exe # Use python icon
    shortcut.save()
    
    print("\n[SUCCESS]")
    print(f"Startup shortcut created successfully at:\n{shortcut_path}")
    print("\nJarvis will now start completely invisibly in the background every time you boot your PC.")
    print("He will remain in 'Sleep Mode' with zero UI until you say 'Wake up Jarvis'.")

if __name__ == "__main__":
    create_startup_shortcut()
