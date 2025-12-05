import os
import time
import subprocess
import re
import collections
import threading

# ----------------------------------------------------------------------
# CONSTANTS & TIMING
# ----------------------------------------------------------------------
BATCH_FILENAME = "mng.txt"
AHK_SCRIPT_NAME = "run_bat.ahk"
HANDSHAKE_FILENAME = "etw_handshake" # No extension needed for scof

# AHK execution buffer
AHK_EXECUTION_TIME = 4.0

# Queue Buffer (Minimum time between batch writes to allow AHK processing)
BATCH_WRITE_COOLDOWN = 0.8

# Log Files
STATS_LOG_BASE = "etw_baseline" 
STATS_LOG_FILENAME = "etw_baseline"

POS_LOG_BASE = "etw_pos"
POS_LOG_FILENAME = "etw_pos"

# Legacy aliases
SCAN_LOG_FILENAME = STATS_LOG_FILENAME 
INV_LOG_FILENAME = STATS_LOG_FILENAME

# Stats to track
STATS_COVERED = [
    "health", "actionpoints", "carryweight", "damageresist", "speedmult",
    "strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck",
    "barter", "bigguns", "energyweapons", "explosives", "lockpick", "medicine",
    "meleeweapons", "repair", "science", "smallguns", "sneak", "speech", "unarmed"
]

# ----------------------------------------------------------------------
# COMMAND QUEUE STATE
# ----------------------------------------------------------------------
_COMMAND_QUEUE = collections.deque()
_QUEUE_LOCK = threading.Lock()
_WORKER_THREAD = None
_SHUTDOWN_FLAG = False

# ----------------------------------------------------------------------
# SMART POLLING
# ----------------------------------------------------------------------

def await_file_creation(path, timeout=15.0, stability_duration=0.5):
    """
    Actively polls for a file to appear and have STABLE content.
    """
    if not path: return None
    path = os.path.normpath(path)
    
    start_time = time.time()
    last_size = -1
    stable_start = 0
    
    while (time.time() - start_time) < timeout:
        exists = os.path.exists(path)
        if exists:
            try:
                os.stat(path)
                current_size = os.path.getsize(path)
                
                if current_size > 0:
                    if current_size == last_size:
                        if (time.time() - stable_start) >= stability_duration:
                            try:
                                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                    lines = f.readlines()
                                    if lines: return lines
                            except PermissionError: pass
                    else:
                        last_size = current_size
                        stable_start = time.time()
            except (OSError, PermissionError) as e:
                print(f"[Bridge] OS Error accessing file: {e}")
        
        time.sleep(0.2)
        
    print(f"[Bridge] TIMEOUT! Could not read file: {path}")
    return None

def read_file_safely(path, retries=20, delay=0.25):
    return await_file_creation(path, timeout=(retries * delay * 2.0))

def write_file_safely(path, content, retries=10, delay=0.1):
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

# ----------------------------------------------------------------------
# CORE COMMAND EXECUTION (Low Level)
# ----------------------------------------------------------------------

def run_console_command(game_path, command_text, ahk_path=None):
    """
    Writes the batch file and triggers AHK. 
    Internal use only - use process_game_commands for logic.
    """
    if not game_path or not os.path.exists(game_path):
        print(f"[Bridge] Game path not found: {game_path}")
        return

    batch_path = os.path.join(game_path, BATCH_FILENAME)
    
    if not ahk_path:
        ahk_path = os.path.abspath(AHK_SCRIPT_NAME)
        
    if write_file_safely(batch_path, command_text):
        try:
            subprocess.Popen([ahk_path], shell=True)
        except Exception as e:
            print(f"Bridge Execution Error: {e}")
    else:
        print("[Bridge] Failed to write batch file.")

# ----------------------------------------------------------------------
# QUEUE WORKER
# ----------------------------------------------------------------------

def _queue_worker_loop(game_path):
    """
    Background thread that processes the command queue sequentially.
    Ensures 'Rapid Fire' commands don't overwrite the batch file before AHK reads it.
    """
    global _WORKER_THREAD
    
    while True:
        batch_to_run = None
        
        with _QUEUE_LOCK:
            if _COMMAND_QUEUE:
                batch_to_run = _COMMAND_QUEUE.popleft()
            else:
                # Queue empty, exit thread
                _WORKER_THREAD = None
                return

        if batch_to_run:
            cmds, ahk_path = batch_to_run
            run_console_command(game_path, "\n".join(cmds), ahk_path)
            # Critical Wait: Allow AHK time to type commands into console
            time.sleep(BATCH_WRITE_COOLDOWN)

def _start_queue_worker_if_needed(game_path):
    global _WORKER_THREAD
    with _QUEUE_LOCK:
        if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
            _WORKER_THREAD = threading.Thread(target=_queue_worker_loop, args=(game_path,), daemon=True)
            _WORKER_THREAD.start()

# ----------------------------------------------------------------------
# VERIFIED COMMAND EXECUTION (The Echo Protocol)
# ----------------------------------------------------------------------

def execute_batch_with_verification(game_path, cmds, ahk_path=None, timeout=8.0):
    """
    Executes a list of commands and waits for a specific 'echo' from the game.
    BLOCKS until the background queue is empty to ensure exclusive access.
    """
    if not game_path or not cmds: return False
    
    # 1. Drain Queue (Exclusive Mode)
    # We wait for pending "Fire & Forget" commands to finish to prevent collision.
    start_wait = time.time()
    while True:
        with _QUEUE_LOCK:
            if not _COMMAND_QUEUE and (_WORKER_THREAD is None or not _WORKER_THREAD.is_alive()):
                break
        if (time.time() - start_wait) > 5.0:
            print("[Bridge] Warning: Queue drain timed out. Forcing verification.")
            break
        time.sleep(0.1)

    # 2. Cleanup old handshake file
    handshake_path = os.path.join(game_path, HANDSHAKE_FILENAME)
    if os.path.exists(handshake_path):
        try: os.remove(handshake_path)
        except: pass
    
    # 3. Construct Verified Batch
    verified_cmds = []
    verified_cmds.append(f"scof {HANDSHAKE_FILENAME}") # Start Log
    verified_cmds.extend(cmds)                         # Payload
    verified_cmds.append("player.GetLevel")            # The Echo
    verified_cmds.append("scof 0")                     # End Log
    
    # 4. Execute Directly (Bypass Queue)
    run_console_command(game_path, "\n".join(verified_cmds), ahk_path)
    
    # 5. Poll for Echo
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        if os.path.exists(handshake_path):
            try:
                with open(handshake_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "GetLevel >>" in content or "GetLevel:" in content:
                        return True
            except:
                pass # Locked, retry
        time.sleep(0.2)
        
    print(f"[Bridge] Verification Timed Out ({timeout}s). Game may be paused or crashed.")
    return False

# ----------------------------------------------------------------------
# PUBLIC API
# ----------------------------------------------------------------------

def process_game_commands(game_path, cmds, ahk_path=None, verify=False):
    """
    Primary entry point for sending commands.
    verify=False: Queues command for background execution (Thread-Safe).
    verify=True: Blocks, drains queue, executes immediately, and waits for confirmation.
    """
    if not cmds: return True
    
    if verify:
        # High Priority / Critical (Extraction, Death)
        success = execute_batch_with_verification(game_path, cmds, ahk_path, timeout=4.0)
        if not success:
            print("[Bridge] CRITICAL: Command batch failed verification!")
        return success
    else:
        # Fire & Forget (UI Clicks, Buying, Selling)
        with _QUEUE_LOCK:
            _COMMAND_QUEUE.append((cmds, ahk_path))
        _start_queue_worker_if_needed(game_path)
        return True

def wait_for_ahk():
    # Legacy wait, kept for safety in synchronous contexts
    time.sleep(0.5)

# ----------------------------------------------------------------------
# UNIFIED BASELINE SCAN
# ----------------------------------------------------------------------

def trigger_stat_scan(game_path, ahk_path=None):
    # Clean up old file
    fp = os.path.join(game_path, STATS_LOG_FILENAME)
    if os.path.exists(fp): 
        try: os.remove(fp)
        except: pass
    time.sleep(0.1)
    
    # Dump Stats
    cmd_lines = [f"scof {STATS_LOG_BASE}"]
    cmd_lines.append("player.getlevel")
    for stat in STATS_COVERED: 
        cmd_lines.append(f"player.getbaseav {stat}")
    cmd_lines.append("player.showinventory")
    cmd_lines.append("scof 0")
    
    # QUEUE this scan to ensure it doesn't overwrite a pending transaction
    process_game_commands(game_path, cmd_lines, ahk_path, verify=False)

# Alias
trigger_baseline_scan = trigger_stat_scan

def read_baseline_scan(game_path):
    if not game_path: return None
    log_path = os.path.join(game_path, STATS_LOG_FILENAME)
    
    lines = await_file_creation(log_path, timeout=15.0)
    if not lines: return None
    
    result = {"level": 1, "stats": {}}
    
    try:
        for line in lines:
            line = line.strip()
            if "GetLevel >>" in line:
                m = re.search(r">> ([\d\.]+)", line)
                if m: result["level"] = float(m.group(1))
            
            if "GetBaseActorValue" in line and ">>" in line:
                parts = line.split(">>")
                if len(parts) == 2:
                    val = float(parts[1].strip())
                    left = parts[0].replace("GetBaseActorValue:", "").strip().lower()
                    if left in STATS_COVERED:
                        result["stats"][left] = val
        return result
    except Exception as e:
        print(f"Bridge Read Error (Stats Parse): {e}")
        return None

# ----------------------------------------------------------------------
# LEGACY REDIRECT
# ----------------------------------------------------------------------

def trigger_inventory_scan(game_path, ahk_path=None):
    trigger_stat_scan(game_path, ahk_path)

# ----------------------------------------------------------------------
# POSITION TRACKING
# ----------------------------------------------------------------------

def trigger_position_dump(game_path, ahk_path=None):
    log_path = os.path.join(game_path, POS_LOG_FILENAME)
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass
    time.sleep(0.1)
    
    cmd_text = f'scof {POS_LOG_BASE}\nplayer.GetPos X\nplayer.GetPos Y\nplayer.GetPos Z\nplayer.GetAngle Z\nscof 0'
    
    # Queue position checks too, to prevent cutting off a raid-start command
    process_game_commands(game_path, [cmd_text], ahk_path, verify=False)

def read_player_position(game_path):
    log_path = os.path.join(game_path, POS_LOG_FILENAME)
    lines = await_file_creation(log_path, timeout=5.0)
    if not lines: return None
    
    pos_data = {}
    content = "".join(lines)
    
    try:
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