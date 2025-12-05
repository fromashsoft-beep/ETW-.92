import tkinter as tk
from tkinter import simpledialog, messagebox
import os
import time
import subprocess
import re
import datetime

# --- CORE CONFIGURATION (Must be set by the user) ---
# IMPORTANT: Replace the placeholder below with your actual Fallout 3 install path.
GAME_PATH = "E:\SteamLibrary\steamapps\common\Fallout 3 goty" 

# --- CONSTANTS FROM ETW BRIDGE ---
BATCH_FILENAME = "mng.txt"
AHK_SCRIPT_NAME = "run_bat.ahk" # Assumes run_bat.ahk is in the same directory as this script.
POS_LOG_BASE = "etw_pos"
POS_LOG_FILENAME = "etw_pos"
LOCATION_LOG_FILE = "locations.txt"
POLLING_INTERVAL_MS = 100
SCAN_TIMEOUT_S = 15.0

# --- UTILITY FUNCTIONS (Adapted from etw_bridge) ---

def write_file_safely(path, content, retries=10, delay=0.1):
    """Safely writes content to a file."""
    if not path: return False
    path = os.path.normpath(path)
    for _ in range(retries):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except (OSError, PermissionError): pass
        except Exception as e: print(f"Bridge Write Error: {e}")
        time.sleep(delay)
    return False

def run_console_command(game_path, command_text, ahk_path=None):
    """Writes the batch file and triggers AHK."""
    if not game_path or not os.path.exists(game_path):
        print(f"[Bridge] Game path not found: {game_path}")
        return

    batch_path = os.path.join(game_path, BATCH_FILENAME)
    
    if not ahk_path:
        ahk_path = os.path.abspath(AHK_SCRIPT_NAME)
        
    if write_file_safely(batch_path, command_text):
        try:
            # Note: shell=True is needed to execute the .ahk file
            subprocess.Popen([ahk_path], shell=True) 
        except Exception as e:
            print(f"Bridge Execution Error: {e}")
    else:
        print("[Bridge] Failed to write batch file.")

def trigger_position_dump(game_path, ahk_path=None):
    """Triggers the game console to dump player position."""
    log_path = os.path.join(game_path, POS_LOG_FILENAME)
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass
    time.sleep(0.1) # Brief pause to ensure file removal registers
    
    # Command to dump X, Y, Z, and Angle Z to the log file
    cmd_text = f'scof {POS_LOG_BASE}\nplayer.GetPos X\nplayer.GetPos Y\nplayer.GetPos Z\nplayer.GetAngle Z\nscof 0'
    run_console_command(game_path, cmd_text, ahk_path)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Position dump triggered.")

def read_player_position(game_path):
    """
    Reads the player's position log non-blockingly.
    Returns: dict if success, None otherwise.
    """
    log_path = os.path.join(game_path, POS_LOG_FILENAME)
    
    if not os.path.exists(log_path): return None
    
    lines = []
    try:
        # Try to read the file quickly without blocking
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            if not lines: return None
    except (OSError, PermissionError):
        return None # File locked, try again next tick
        
    pos_data = {}
    content = "".join(lines)
    
    try:
        # Use simple regex pattern matching to pull the coordinate values
        x_match = re.search(r"(?:X\s*[:=]*\s*|X\s*>>\s*|X\s+)([-\d.]+)", content, re.IGNORECASE)
        y_match = re.search(r"(?:Y\s*[:=]*\s*|Y\s*>>\s*|Y\s+)([-\d.]+)", content, re.IGNORECASE)
        z_match = re.search(r"(?:Z\s*[:=]*\s*|Z\s*>>\s*|Z\s+)([-\d.]+)", content, re.IGNORECASE)
        angle_match = re.search(r"(?:Angle\s*[:=]*\s*|Angle\s*>>\s*|GetAngle:?\s*Z\s*>>\s*)([-\d.]+)", content, re.IGNORECASE)
        
        if x_match and y_match and z_match:
            pos_data["x"] = float(x_match.group(1))
            pos_data["y"] = float(y_match.group(1))
            pos_data["z"] = float(z_match.group(1))
            pos_data["angle"] = float(angle_match.group(1)) if angle_match else 0.0
            return pos_data
    except Exception as e:
        print(f"Bridge Read Error (Pos): {e}")
        
    return None

def write_location_to_file(log_entry):
    """Appends the formatted log entry to locations.txt."""
    try:
        with open(LOCATION_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Location logged successfully.")
    except Exception as e:
        print(f"ERROR: Could not write to log file: {e}")

# --- APPLICATION CLASS ---

class PositionLoggerApp:
    def __init__(self, master):
        self.master = master
        master.title("Position Logger (ETW Bridge)")
        master.geometry("300x150")
        master.configure(bg="#222222")
        
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.is_scan_pending = False
        self.scan_start_time = 0
        self.log_file_path = os.path.join(os.getcwd(), LOCATION_LOG_FILE)
        
        if not GAME_PATH or not os.path.exists(GAME_PATH):
            self.status_text = "ERROR: Set GAME_PATH in script."
            self.status_color = "#FF4444"
            self.can_run = False
        else:
            self.status_text = "Ready. Press [ in-game."
            self.status_color = "#00FF00"
            self.can_run = True
            try:
                import keyboard
                keyboard.add_hotkey('[', self.handle_hotkey_press)
                self.keyboard = keyboard
            except ImportError:
                self.status_text = "ERROR: Python 'keyboard' module required."
                self.status_color = "#FF4444"
                self.can_run = False
                
        self.status_label = tk.Label(master, text=self.status_text, bg="#222222", fg=self.status_color, font=("Courier", 10))
        self.status_label.pack(pady=20)
        
        self.log_path_label = tk.Label(master, text=f"Log: {LOCATION_LOG_FILE}", bg="#222222", fg="#AAAAAA", font=("Courier", 9))
        self.log_path_label.pack()
        
        self.last_pos_label = tk.Label(master, text="Waiting for scan...", bg="#222222", fg="#888888", font=("Courier", 9))
        self.last_pos_label.pack()
        
    def handle_hotkey_press(self):
        """Called when '[' is pressed globally."""
        if not self.can_run:
            print("Cannot run: Configuration error.")
            return
            
        if self.is_scan_pending:
            self.update_status("Scan already in progress...", "#FFFF00")
            return

        self.is_scan_pending = True
        self.scan_start_time = time.time()
        self.update_status("Triggering position dump (Game must be unpaused)...", "#FFFF00")
        
        # 1. Trigger the actual dump via the Bridge
        trigger_position_dump(GAME_PATH)
        
        # 2. Start the non-blocking polling loop
        self.master.after(POLLING_INTERVAL_MS, self.poll_for_position)

    def poll_for_position(self):
        """Non-blocking function that checks for the log file results."""
        if not self.is_scan_pending:
            return

        pos_data = read_player_position(GAME_PATH)

        if pos_data:
            # Success!
            self.is_scan_pending = False
            self.prompt_for_description(pos_data)
        else:
            # Check for timeout
            elapsed = time.time() - self.scan_start_time
            if elapsed > SCAN_TIMEOUT_S:
                self.is_scan_pending = False
                self.update_status("Scan TIMEOUT! (Game paused or crashed?)", "#FF4444")
            else:
                # Retry
                self.update_status(f"Waiting for game log ({int(elapsed)}s)...", "#FFFF00")
                self.master.after(POLLING_INTERVAL_MS, self.poll_for_position)

    def prompt_for_description(self, pos_data):
        """Opens a Tkinter dialog box for user input."""
        # Hide main window to focus on the dialog
        self.master.withdraw() 
        
        description = simpledialog.askstring(
            "Location Description", 
            "Enter a short description for this location:", 
            parent=self.master
        )

        # Show main window again
        self.master.deiconify() 
        
        if description:
            self.log_position(pos_data, description)
        else:
            self.update_status("Location log cancelled by user.", "#AAAAAA")
            
    def log_position(self, pos_data, description):
        """Formats and logs the final data."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        entry = (
            f"[{timestamp}] "
            f"'{description.strip()}' | "
            f"X: {pos_data['x']:.2f}, Y: {pos_data['y']:.2f}, Z: {pos_data['z']:.2f}, "
            f"Angle Z: {pos_data['angle']:.2f}"
        )
        write_location_to_file(entry)
        
        self.last_pos_label.config(text=f"Last Log: X:{pos_data['x']:.0f}, Y:{pos_data['y']:.0f}, Z:{pos_data['z']:.0f}")
        self.update_status("Location logged successfully!", "#00FF00")
        
    def update_status(self, text, color):
        self.status_label.config(text=text, fg=color)
        self.master.update()
        
    def on_closing(self):
        """Cleanup hotkeys on close."""
        if hasattr(self, 'keyboard'):
            self.keyboard.unhook_all()
        self.master.destroy()

if __name__ == "__main__":
    try:
        import keyboard
    except ImportError:
        print("\nCRITICAL: The 'keyboard' module is required. Install with: pip install keyboard")
        sys.exit(1)
        
    root = tk.Tk()
    app = PositionLoggerApp(root)
    root.mainloop()