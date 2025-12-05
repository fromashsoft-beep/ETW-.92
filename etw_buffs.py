# Foundation
import etw_config as config
import etw_io as io

# Note: We do NOT import etw_engine here to avoid circular loops.
# We access save_data directly passed as arguments.

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------

# Base buff percentage by companion level (0.02 = 2%)
COMPANION_BUFF_SCALING = {
    1: 0.02,
    2: 0.04,
    3: 0.06,
    4: 0.08,
    5: 0.10
}

# ----------------------------------------------------------------------
# COMPANION CALCULATIONS
# ----------------------------------------------------------------------

def calculate_companion_bonuses(save_data, task_tags=None, raid_tags=None):
    """
    Returns a dict of multipliers based on the currently active companion's state.
    Includes Level scaling, Loyalty bonuses, and Contextual (Tag) bonuses.
    """
    bonuses = {
        "xp": 1.0, "caps": 1.0, "scrip": 1.0, 
        "loot": 1.0, "damage": 1.0, "defense": 1.0,
        "carry_weight": 1.0, "move_speed": 1.0, 
        "hp": 1.0, "ap": 1.0
    }
    
    # 1. Get Active Companion Data manually
    g_state = save_data.get("global_companion_state", {})
    active_id = g_state.get("active_companion_id")
    
    if not active_id or active_id not in save_data.get("companions", {}):
        return bonuses
        
    c_data = save_data["companions"][active_id]
    
    # Load Roster Config via IO/Config (Fixing the crash here)
    roster = io.load_json(config.PATHS["content_companions"], {})
    c_def = roster.get(active_id)
    if not c_def: return bonuses
    
    # 2. Base Buff Calculation
    level = c_data.get("level", 1)
    base_pct = COMPANION_BUFF_SCALING.get(level, 0.02)
    
    if c_data.get("loyalty_completed"):
        base_pct += 0.05
        
    buff_type = c_def.get("base_buff_type")
    if buff_type in bonuses:
        bonuses[buff_type] += base_pct
        
    # 3. Task Tag Bonus (+10%)
    if task_tags:
        c_tags = set(c_def.get("task_tags", []))
        t_tags = set(task_tags)
        if not c_tags.isdisjoint(t_tags):
            bonuses["xp"] += 0.10
            bonuses["caps"] += 0.10
            bonuses["scrip"] += 0.10
            bonuses["loot"] += 0.10
            
    # 4. Raid Tag Bonus (+10%)
    if raid_tags:
        c_raid_tags = set(c_def.get("raid_tags", []))
        r_tags = set(raid_tags)
        if not c_raid_tags.isdisjoint(r_tags):
            bonuses["xp"] += 0.10
            bonuses["caps"] += 0.10
            bonuses["scrip"] += 0.10
            bonuses["loot"] += 0.10
            
    return bonuses

# ----------------------------------------------------------------------
# HIDEOUT CALCULATIONS
# ----------------------------------------------------------------------

def get_hideout_buffs(save_data):
    """
    Iterates through built stations to find passive buffs.
    """
    mods = {"xp_mult": 0.0, "caps_mult": 0.0, "fortune_flat": 0.0}
    
    stations = save_data.get("hideout_stations", {})
    # Use IO/Config here - This was the line causing the AttributeError
    content = io.load_json(config.PATHS["content_hideout"])
    
    for s_conf in content.get("stations", []):
        s_id = s_conf["id"]
        
        if s_conf.get("type") != "passive_buff": continue
        
        user_data = stations.get(s_id)
        if not user_data: continue
        
        level = user_data.get("level", 0)
        if level < 1: continue
        
        lvl_conf = next((l for l in s_conf["levels"] if l["level"] == level), None)
        if not lvl_conf: continue
        
        buff = lvl_conf.get("buff", {})
        b_type = buff.get("type")
        b_val = buff.get("value", 0.0)
        
        if b_type in mods:
            mods[b_type] += b_val
            
    return mods

# ----------------------------------------------------------------------
# AGGREGATE CALCULATORS
# ----------------------------------------------------------------------

def get_player_modifiers(save_data):
    """
    Combines Active Buffs, Hideout Buffs, and Companion Bonuses into a single modifier set.
    """
    mods = {
        "xp_mult": 1.0, 
        "caps_mult": 1.0, 
        "scrip_mult": 1.0, 
        "loot_count_bonus": 0, 
        "effective_fortune": save_data.get("fortune", 0.0)
    }
    
    # Process Consumable Buffs
    buffs = save_data.get("active_buffs", [])
    for b in buffs:
        bid = b.get("id")
        if bid == "xp_boost": mods["xp_mult"] += 0.25
        elif bid == "caps_boost": mods["caps_mult"] += 0.25
        elif bid == "scrip_boost": mods["scrip_mult"] += 0.25
        elif bid == "loot_quantity": mods["loot_count_bonus"] += 1
        elif bid == "fortune_boost": mods["effective_fortune"] += 2.0
        elif bid == "rested_xp": mods["xp_mult"] += 0.25
    
    # Hideout Buffs
    h_buffs = get_hideout_buffs(save_data)
    mods["xp_mult"] += h_buffs.get("xp_mult", 0.0)
    mods["caps_mult"] += h_buffs.get("caps_mult", 0.0)
    mods["effective_fortune"] += h_buffs.get("fortune_flat", 0.0)
    
    # Companion Bonuses
    c_bonuses = calculate_companion_bonuses(save_data)
    mods["xp_mult"] += (c_bonuses["xp"] - 1.0)
    mods["caps_mult"] += (c_bonuses["caps"] - 1.0)
    mods["scrip_mult"] += (c_bonuses["scrip"] - 1.0)
    
    return mods

def calculate_cumulative_multiplier(save_data, stat_type):
    """
    Calculates the total bonus percentage for a specific stat.
    """
    total_bonus = 0.0
    
    # Consumables
    buffs = save_data.get("active_buffs", [])
    for b in buffs:
        bid = b.get("id")
        if stat_type == "xp" and (bid == "xp_boost" or bid == "rested_xp"): 
            total_bonus += 0.25
        elif stat_type == "caps" and bid == "caps_boost": 
            total_bonus += 0.25
        elif stat_type == "scrip" and bid == "scrip_boost": 
            total_bonus += 0.25
    
    # Hideout
    h_buffs = get_hideout_buffs(save_data)
    if stat_type == "xp": total_bonus += h_buffs.get("xp_mult", 0.0)
    elif stat_type == "caps": total_bonus += h_buffs.get("caps_mult", 0.0)
    
    # Companions
    c_bonuses = calculate_companion_bonuses(save_data)
    if stat_type in c_bonuses:
        total_bonus += (c_bonuses[stat_type] - 1.0)
        
    return 1.0 + total_bonus