"""
tools/sys_core.py - Windows 11 System Control Module
====================================================
Project: DAA Digital Advanced Assistant
OS Target: Windows 11 Only
Description: Handles OS-level commands like locking the screen,
             minimizing windows, or launching system apps via WinAPI.
"""

import ctypes       # Allows calling functions in DLLs (Dynamic Link Libraries)
import subprocess   # Used to spawn new processes (open apps)
import pyautogui    # Simulates keyboard presses (hotkeys)
from datetime import datetime

def execute_sys_command(command):
    """
    Parses and executes a Windows system command received from the AI Brain.

    Args:
        command (str): The specific action keyword (e.g., 'lock', 'calc').

    Returns:
        str: A log message indicating success or failure to be sent back to the GUI.
    """
    cmd = command.strip().lower()
    print(f"[SYS_CORE] Executing Windows command: {cmd}")

    try:
        # --- ACTION: LOCK WORKSTATION ---
        # "lock" -> Immediately locks the PC (Login screen).
        # We use 'ctypes' to call the 'LockWorkStation' function directly from 'user32.dll'.
        # This is the most secure and native way to lock Windows programmatically.
        if cmd == "lock":
            ctypes.windll.user32.LockWorkStation()
            return "Windows Workstation locked."

        # --- ACTION: MINIMIZE ALL (SHOW DESKTOP) ---
        # "minimize" / "desktop" -> Toggles the desktop view.
        # We simulate the keyboard shortcut 'Windows Key + D'.
        elif cmd == "minimize" or cmd == "desktop":
            pyautogui.hotkey('win', 'd')
            return "Toggled Desktop View (Win+D)."

        # --- ACTION: CALCULATOR ---
        # "calc" -> Launches the native Windows Calculator.
        # We use Popen (Process Open) so it doesn't block the Python script while running.
        elif cmd == "calc":
            subprocess.Popen("calc.exe")
            return "Calculator launched."

        # --- ACTION: SCREENSHOT (LOCAL SAVE) ---
        # "screenshot" -> Saves a snapshot locally to the client folder.
        # Note: The AI usually gets the image via RAM (base64), this is just for file backup.
        elif cmd == "screenshot":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"daa_screenshot_{timestamp}.png"
            pyautogui.screenshot(filename)
            return f"Screenshot saved to disk: {filename}"

        # --- ACTION: WINDOWS UPDATE ---
        # "update" -> Opens the Windows Update settings page directly.
        elif cmd == "update":
            # "start" is a shell command, so we need shell=True
            subprocess.Popen("start ms-settings:windowsupdate", shell=True)
            return "Windows Update settings opened."

        # --- UNKNOWN COMMAND ---
        else:
            return f"Unknown Windows command: {cmd}"

    except Exception as e:
        # Catch any system errors (e.g., permission denied) and return the error text.
        error_msg = f"Windows System Error: {str(e)}"
        print(f"[SYS_CORE ERROR] {error_msg}")
        return error_msg