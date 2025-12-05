import random
import time

# Foundation
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_bridge as bridge

# --------------------------
# 1. AMBUSH CONSTANTS
# --------------------------
MIN_SECONDS_BEFORE_FIRST_AMBUSH = 300 
MIN_SECONDS_BETWEEN_AMBUSHES = 300    
BASE_AMBUSH_CHANCE_PER_TICK = 0.005   
AMBUSH_THREAT_FACTOR = 0.002          

_AMBUSHES = None 

def _load_ambushes():
    """Lazy load static data."""
    global _AMBUSHES
    if _AMBUSHES is None:
        try:
            # Refactored to use IO/Config
            _AMBUSHES = io.load_json(config.PATHS["ambushes"], [])
        except AttributeError:
             _AMBUSHES = []

# --------------------------
# 2. POSITION TRACKING
# --------------------------

def get_player_position_with_retry(game_path):
    """
    Fetches player coordinates using the Bridge's smart polling.
    """
    bridge.trigger_position_dump(game_path)
    pos = bridge.read_player_position(game_path)
    return pos

# --------------------------
# 3. AMBUSH LOGIC
# --------------------------

def check_ambush_trigger(save_data, elapsed_time, force=False):
    """
    Determines if an ambush SHOULD trigger.
    Returns True if conditions are met, False otherwise.
    Does NOT execute the spawn.
    """
    # Safety Check: Only allow ambushes if Raid is Active
    if not save_data.get("raid_active", False):
        return False

    if force:
        pass
    else:
        mod_id = save_data.get("current_raid_modifier")
        
        if mod_id == "watching_eyes":
            return False 
                         
        if elapsed_time < MIN_SECONDS_BEFORE_FIRST_AMBUSH: return False
        
        amb_state = save_data.get("ambush_state", {})
        last_time = amb_state.get("last_check_time", 0.0)
        now = time.time()
        
        cooldown = MIN_SECONDS_BETWEEN_AMBUSHES
        
        if mod_id == "hostile_wasteland":
            cooldown = 120 
            
        if (now - last_time) < cooldown: return False
        
        threat = int(save_data.get("threat_level", 0))
        chance = BASE_AMBUSH_CHANCE_PER_TICK + (threat * AMBUSH_THREAT_FACTOR)
        
        if mod_id == "hostile_wasteland":
            chance += 0.05 
            
        if random.random() > chance: return False

    # Update state immediately to prevent double-triggering
    amb_state = save_data.get("ambush_state", {})
    amb_state["last_check_time"] = time.time()
    save_data["ambush_state"] = amb_state
    io.save_json(config.PATHS["save_data"], save_data)
    
    return True

def prepare_ambush_coords(save_data):
    """
    Step 1: Get the player's current position to lock in the ambush site.
    Returns a dict with coordinates and the chosen enemy group, or None on failure.
    """
    _load_ambushes()
    
    game_path = save_data.get("game_install_path", "")
    if not game_path: return None
    
    # This call might take a moment as it polls the bridge
    pos = get_player_position_with_retry(game_path)
    
    if not pos: 
        print("Ambush Prep Failed: Could not get player position.")
        return None
        
    threat = save_data.get("threat_level", 1)
    eligible = [g for g in _AMBUSHES if g.get("threat_tier", 1) <= (threat + 1)]
    if not eligible: return None
    
    group = random.choice(eligible)
    
    return {
        "position": pos,
        "group": group
    }

def execute_ambush_spawn(save_data, ambush_data):
    """
    Step 2: Execute the spawn commands using the pre-calculated data.
    CRITICAL: Uses verify=False to avoid handshake delay, ensuring spawn timing is tight.
    """
    if not ambush_data: return

    game_path = save_data.get("game_install_path", "")
    if not game_path: return
    
    pos = ambush_data["position"]
    group = ambush_data["group"]
    
    lines = []
    
    # Spawn Enemies around the locked position
    for s in group.get("spawn", []):
        if s.get("code"): 
            off_x = random.randint(-1000, 1000)
            off_y = random.randint(-1000, 1000)
            
            # Ensure minimum distance
            if abs(off_x) < 300: off_x = 300 if off_x > 0 else -300
            if abs(off_y) < 300: off_y = 300 if off_y > 0 else -300
            
            # Note: We spawn "at me" (player's current location), then teleport player back to 'pos'
            # OR we can spawn at specific coords if the engine supports it easily.
            # Using 'placeatme' is relative to the player object. 
            # If the player has moved significantly during the 3-8s delay, 'placeatme' spawns them at the *new* location.
            # To simulate an "Ambush waiting for you", we teleport the player back to 'pos' (the location 5s ago).
            
            lines.append(f"player.placeatme {s['code']} 1")
    
    # Teleport Player BACK to the ambush site (The "Trap")
    if pos:
        lines.append(f"player.setpos x {pos['x']}")
        lines.append(f"player.setpos y {pos['y']}")
        lines.append(f"player.setpos z {pos['z']}")
        lines.append(f"player.setangle z {pos['angle']}")
        
    if lines:
        # OPT-OUT of verification for speed
        bridge.process_game_commands(game_path, lines, verify=False)
        bridge.wait_for_ahk() # Small legacy buffer just in case
        
        # Track stats
        amb_state = save_data.get("ambush_state", {})
        amb_state["ambushes_triggered"] = amb_state.get("ambushes_triggered", 0) + 1
        save_data["ambush_state"] = amb_state
        io.save_json(config.PATHS["save_data"], save_data)