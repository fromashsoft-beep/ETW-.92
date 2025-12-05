import random
import math

# Foundation Modules
import etw_config as config
import etw_io as io

# Note: engine imported ONLY for types/constants if strictly needed, 
# but preferably avoided to keep clean architecture.
# We remove 'import etw_engine as engine' to force clean usage.

# ----------------------------------------------------------------------
# 1. CONSTANTS & ROSTER
# ----------------------------------------------------------------------

LEVEL_XP_THRESHOLDS = {
    1: 0,
    2: 1000,
    3: 4000,
    4: 10000,
    5: 20000
}

# Base buff percentage by level (0.02 = 2%)
BUFF_SCALING = {
    1: 0.02,
    2: 0.04,
    3: 0.06,
    4: 0.08,
    5: 0.10
}

COMPANION_XP_SHARE = 0.25
BAR_MAX_SLOTS = 3
BAR_APPEAR_CHANCE = 0.50 
ULTIMATE_FILL_TIME = 30.0

DEFAULT_MILESTONES = {
    "first_extended_raid": False,
    "three_successful_raids": False,
    "first_emergency_task": False,
    "first_bonus_objective": False,
    "five_bonus_objectives_total": False,
    "first_hideout_workstation": False,
    "all_difficulties_cleared": False,
    "first_task_completed": False, 
    "first_sos_flare": False,
    "first_threat_level_5": False,
    "first_death": False,
    "fifty_scrip": False,
    "tasks_completed_count": 0,
    "bonus_objs_count": 0,
    "diff_cleared_easy": False,
    "diff_cleared_medium": False,
    "diff_cleared_hard": False
}

# --- CACHING OPTIMIZATION ---
_ROSTER_CACHE = None

def load_companion_roster():
    """
    Loads the static companion definitions from JSON.
    Uses caching to prevent redundant disk I/O.
    """
    global _ROSTER_CACHE
    if _ROSTER_CACHE is None:
        _ROSTER_CACHE = io.load_json(config.PATHS["content_companions"], {})
    return _ROSTER_CACHE

# ----------------------------------------------------------------------
# 2. STATE MANAGEMENT
# ----------------------------------------------------------------------

def initialize_companion_state(save_data):
    """
    Ensures the save data has the necessary structures for the companion system.
    """
    roster = load_companion_roster()
    
    if "companions" not in save_data:
        save_data["companions"] = {}
        
    for c_id in roster:
        if c_id not in save_data["companions"]:
            save_data["companions"][c_id] = {
                "unlocked": False,
                "level": 1,
                "xp": 0,
                "loyalty_unlocked": False,
                "loyalty_completed": False,
                "visible_in_bar": False,
                "pending_slot": False,
                "ultimate_progress": 0.0
            }
            
    if "global_companion_state" not in save_data:
        save_data["global_companion_state"] = {
            "active_companion_id": None,
            "bar_slots": [None, None, None], 
            "milestones": DEFAULT_MILESTONES.copy() 
        }
    else:
        # Backfill milestones
        ms = save_data["global_companion_state"].get("milestones", {})
        merged_milestones = DEFAULT_MILESTONES.copy()
        merged_milestones.update(ms) 
        save_data["global_companion_state"]["milestones"] = merged_milestones


def get_active_companion(save_data):
    """Returns the ID and Data of the active companion, or None."""
    g_state = save_data.get("global_companion_state", {})
    active_id = g_state.get("active_companion_id")
    if active_id and active_id in save_data.get("companions", {}):
        return active_id, save_data["companions"][active_id]
    return None, None

def set_active_companion(save_data, companion_id):
    """Sets the active companion. Returns success bool."""
    if "global_companion_state" not in save_data:
        initialize_companion_state(save_data)
        
    if companion_id not in save_data.get("companions", {}): return False
    if not save_data["companions"][companion_id]["unlocked"]: return False
    
    save_data["global_companion_state"]["active_companion_id"] = companion_id
    return True

# ----------------------------------------------------------------------
# 3. MILESTONE LOGIC
# ----------------------------------------------------------------------

def check_milestones(save_data, context):
    """
    Central hub for checking unlocks.
    """
    if "global_companion_state" not in save_data:
        initialize_companion_state(save_data)
        
    g_state = save_data.get("global_companion_state", {})
    ms = g_state.get("milestones", {})
    
    ms_merged = DEFAULT_MILESTONES.copy()
    ms_merged.update(ms)
    ms = ms_merged
    save_data["global_companion_state"]["milestones"] = ms 
    
    updated = False
    roster = load_companion_roster() 

    # Event: Raid End
    if context.get("event") == "raid_end":
        duration = context.get("duration", 0) / 60.0
        
        if duration > 45 and not ms.get("first_extended_raid"):
            ms["first_extended_raid"] = True; updated = True
            
        if context.get("emergency_count", 0) > 0 and not ms.get("first_emergency_task"):
            ms["first_emergency_task"] = True; updated = True
            
        if context.get("bonus_count", 0) > 0:
            if not ms.get("first_bonus_objective"):
                ms["first_bonus_objective"] = True; updated = True
            ms["bonus_objs_count"] = ms.get("bonus_objs_count", 0) + context["bonus_count"]
            if ms["bonus_objs_count"] >= 5 and not ms.get("five_bonus_objectives_total"):
                ms["five_bonus_objectives_total"] = True; updated = True
                
        if context.get("death_occurred") and not ms.get("first_death"):
            ms["first_death"] = True; updated = True
            
        if context.get("sos_used") and not ms.get("first_sos_flare"):
            ms["first_sos_flare"] = True; updated = True
            
        threat = save_data.get("threat_level", 1)
        if threat >= 5 and context.get("success") and not ms.get("first_threat_level_5"):
            ms["first_threat_level_5"] = True; updated = True

        consecutive_extractions = save_data.get("consecutive_extractions", 0)
        if consecutive_extractions >= 3 and not ms.get("three_successful_raids"):
            ms["three_successful_raids"] = True; updated = True
            
    # Event: Task Completed
    if context.get("event") == "task_complete":
        if not ms.get("first_task_completed"): 
            ms["first_task_completed"] = True; updated = True
            
        ms["tasks_completed_count"] = ms.get("tasks_completed_count", 0) + 1
        
        diff = context.get("difficulty")
        if diff == "easy": ms["diff_cleared_easy"] = True
        elif diff == "medium": ms["diff_cleared_medium"] = True
        elif diff == "hard": ms["diff_cleared_hard"] = True
        
        if ms.get("diff_cleared_easy") and ms.get("diff_cleared_medium") and ms.get("diff_cleared_hard") and not ms.get("all_difficulties_cleared"):
            ms["all_difficulties_cleared"] = True; updated = True

    # Event: Scrip Check
    if save_data.get("scrip", 0) >= 50 and not ms.get("fifty_scrip"):
        ms["fifty_scrip"] = True; updated = True
        
    # Event: Hideout Unlock
    stations = save_data.get("hideout_stations", {})
    has_station = any(s.get("level", 0) > 0 for s in stations.values())
    if has_station and not ms.get("first_hideout_workstation"):
        ms["first_hideout_workstation"] = True; updated = True

    if updated:
        _update_pending_slots(save_data, len(roster))

def _update_pending_slots(save_data, roster_size):
    """
    Calculates total earned slots vs total assigned slots.
    """
    if "global_companion_state" not in save_data:
        initialize_companion_state(save_data)
        
    g_state = save_data.get("global_companion_state", {})
    ms = g_state.get("milestones", {})
    comps = save_data.get("companions", {})
    
    # 1. Calculate Earned Slots
    earned = 0
    if ms.get("first_extended_raid"): earned += 1
    if ms.get("three_successful_raids"): earned += 1 
    if ms.get("first_emergency_task"): earned += 1
    if ms.get("first_bonus_objective"): earned += 1
    if ms.get("five_bonus_objectives_total"): earned += 1
    if ms.get("first_hideout_workstation"): earned += 1
    if ms.get("all_difficulties_cleared"): earned += 1
    if ms.get("first_task_completed"): earned += 1
    if ms.get("first_sos_flare"): earned += 1
    if ms.get("first_threat_level_5"): earned += 1
    if ms.get("first_death"): earned += 1
    if ms.get("fifty_scrip"): earned += 1
    earned += (ms.get("tasks_completed_count", 0) // 5)
    
    earned = min(earned, roster_size)
    
    # 2. Count Assigned Slots
    assigned_count = 0
    candidates = []
    
    for c_id, c_data in comps.items():
        if c_data.get("unlocked") or c_data.get("pending_slot"):
            assigned_count += 1
        else:
            candidates.append(c_id)
            
    # 3. Assign New Slots
    while assigned_count < earned and candidates:
        choice = random.choice(candidates)
        comps[choice]["pending_slot"] = True
        candidates.remove(choice)
        assigned_count += 1

# ----------------------------------------------------------------------
# 4. BAR / RECRUITMENT LOGIC
# ----------------------------------------------------------------------

def roll_daily_bar_spawns(save_data):
    """
    Run on Day Advance / Return to Town.
    """
    roster = load_companion_roster()
    _update_pending_slots(save_data, len(roster)) 
    
    g_state = save_data.get("global_companion_state", {})
    comps = save_data.get("companions", {})
    bar_slots = g_state.get("bar_slots", [None]*BAR_MAX_SLOTS)
    if len(bar_slots) != BAR_MAX_SLOTS: bar_slots = [None]*BAR_MAX_SLOTS
    
    empty_indices = [i for i, slot in enumerate(bar_slots) if slot is None]
    if not empty_indices: return 
    
    candidates = []
    current_bar_ids = [s for s in bar_slots if s]
    
    for c_id, c_data in comps.items():
        if c_data.get("pending_slot") and not c_data.get("unlocked") and c_id not in current_bar_ids:
            candidates.append(c_id)
            
    for idx in empty_indices:
        if not candidates: break
        if random.random() < BAR_APPEAR_CHANCE:
            chosen = random.choice(candidates)
            candidates.remove(chosen)
            bar_slots[idx] = chosen
            comps[chosen]["visible_in_bar"] = True
            
    g_state["bar_slots"] = bar_slots

def get_recruitment_quest_params(companion_id):
    """
    Returns the config needed for the Engine to generate a Side Quest.
    """
    roster = load_companion_roster()
    c_def = roster.get(companion_id)
    if not c_def: return None
    
    quest_def = c_def.get("quest_recruit", {})
    
    return {
        "companion_id": companion_id,
        "type": "companion_recruitment",
        "title": quest_def.get("title", f"Recruit {c_def['name']}"),
        "flavor_text": quest_def.get("flavor_text", c_def["personality"]),
        "difficulty": "medium",
        "reward_type": "recruit_companion"
    }

def complete_recruitment(save_data, companion_id):
    """Finalizes recruitment."""
    if companion_id not in save_data.get("companions", {}): return
    
    c_data = save_data["companions"][companion_id]
    c_data["unlocked"] = True
    c_data["visible_in_bar"] = False
    c_data["pending_slot"] = True 
    
    g_state = save_data.get("global_companion_state", {})
    slots = g_state.get("bar_slots", [])
    for i in range(len(slots)):
        if slots[i] == companion_id:
            slots[i] = None
    g_state["bar_slots"] = slots

# ----------------------------------------------------------------------
# 5. PROGRESSION & BUFFS
# ----------------------------------------------------------------------

def add_companion_xp(save_data, player_xp_amount):
    """
    Adds 25% of player XP to the active companion.
    """
    active_id, c_data = get_active_companion(save_data)
    if not c_data: return 0
    
    share = int(player_xp_amount * COMPANION_XP_SHARE)
    if share <= 0: return 0
    
    c_data["xp"] += share
    
    current_xp = c_data["xp"]
    new_level = 1
    for lvl in range(5, 0, -1):
        if current_xp >= LEVEL_XP_THRESHOLDS[lvl]:
            new_level = lvl
            break
            
    if new_level > c_data["level"]:
        c_data["level"] = new_level
        if new_level >= 5 and not c_data["loyalty_unlocked"]:
            c_data["loyalty_unlocked"] = True
            
    return share

def update_ultimate_progress(save_data, minutes_elapsed):
    """
    Adds raid time to ultimate charge.
    """
    active_id, c_data = get_active_companion(save_data)
    if not c_data: return
    
    if c_data.get("level", 1) < 5 or not c_data.get("loyalty_completed"):
        return

    fraction = minutes_elapsed / ULTIMATE_FILL_TIME
    c_data["ultimate_progress"] = min(1.0, c_data["ultimate_progress"] + fraction)

def get_loyalty_quest_params(companion_id):
    """
    Returns params for generating the Loyalty Quest.
    """
    roster = load_companion_roster()
    c_def = roster.get(companion_id)
    if not c_def: return None
    
    quest_def = c_def.get("quest_loyalty", {})
    
    return {
        "companion_id": companion_id,
        "type": "companion_loyalty",
        "title": quest_def.get("title", f"{c_def['name']}'s Request"),
        "flavor_text": quest_def.get("flavor_text", "I've got a personal matter to settle. (Loyalty Mission)"),
        "difficulty": "hard",
        "reward_type": "loyalty_complete"
    }

def complete_loyalty(save_data, companion_id):
    if companion_id not in save_data.get("companions", {}): return
    save_data["companions"][companion_id]["loyalty_completed"] = True