import time
import etw_engine as engine
import etw_ambush as ambush
import etw_companions as companions

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
SOS_UNLOCK_TIME = 1500 # 25 Minutes
SPICY_LIMIT_TIME = 900 # 15 Minutes

# ----------------------------------------------------------------------
# CORE TICK LOGIC
# ----------------------------------------------------------------------

def process_game_tick(save_data):
    """
    Called every second by the main UI loop.
    Calculates game state updates based on elapsed raid time.
    Returns a status dictionary for the UI to render.
    """
    status = {
        "is_active": False,
        "elapsed_seconds": 0,
        "is_paused": False,
        "ambush_triggered": False,
        "sos_ready": False,
        "sos_text": "SOS (0)",
        "sos_state": "disabled",
        "fail_state": None # None, "DIED", or "FAILED (Time)"
    }

    if not save_data.get("raid_active"):
        return status

    status["is_active"] = True
    
    # 1. Calculate Time
    start_t = save_data.get("last_raid_start_timestamp", time.time())
    now = time.time()
    raw_elapsed = now - start_t
    paused_total = save_data.get("raid_paused_elapsed", 0.0)
    
    # Check Pause State
    if save_data.get("raid_paused", False):
        status["is_paused"] = True
        # If paused, we don't update game logic, just return status
        return status

    # Effective elapsed time
    elapsed = raw_elapsed - paused_total
    save_data["last_raid_duration"] = elapsed
    status["elapsed_seconds"] = elapsed

    # 2. Ambush Logic
    # REFACTORED: We check if an ambush SHOULD happen.
    # If yes, we flag it in the status. The UI Controller (ETW_App) will handle the execution sequence.
    # We do NOT call execute_ambush_spawn here anymore.
    if ambush.check_ambush_trigger(save_data, elapsed):
        status["ambush_triggered"] = True

    # 3. Companion Ultimate Progress
    # Updates the float value in save_data directly
    companions.update_ultimate_progress(save_data, elapsed / 60.0)

    # 4. Check Raid Modifiers (Fail States & SOS)
    mod_id = save_data.get("current_raid_modifier", "")
    is_spicy = (mod_id == "spicy_sieverts")
    
    # SOS Logic
    inv = save_data.get("inventory", {})
    has_flare = inv.get("sos_flare", 0) > 0
    
    if is_spicy:
        status["sos_text"] = "SOS (DISABLED)"
        status["sos_state"] = "disabled"
        
        # Time Limit Check
        rem_sec = SPICY_LIMIT_TIME - elapsed
        if rem_sec <= 0:
            status["fail_state"] = "FAILED (00:00)"
        else:
            r_m = int(rem_sec // 60)
            r_s = int(rem_sec % 60)
            status["fail_state"] = f"DIED ({r_m:02}:{r_s:02})"
            
    elif has_flare:
        if elapsed >= SOS_UNLOCK_TIME:
            status["sos_ready"] = True
            status["sos_text"] = "SOS FLARE"
            status["sos_state"] = "normal"
        else:
            rem = SOS_UNLOCK_TIME - elapsed
            rem_m = int(rem // 60)
            rem_s = int(rem % 60)
            status["sos_text"] = f"SOS ({rem_m:02}:{rem_s:02})"
            status["sos_state"] = "disabled"
    else:
        status["sos_text"] = "SOS (0)"
        status["sos_state"] = "disabled"

    # Default Fail State (if not overridden by modifier)
    if status["fail_state"] is None:
        status["fail_state"] = "DIED"

    return status