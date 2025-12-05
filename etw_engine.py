import math
import random
import time

# Foundation Modules (The New Base)
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_bridge as bridge
import etw_buffs as buffs
import etw_tasks as tasks
import etw_companions as companions
import etw_hideout
import etw_task_generator as task_gen
import etw_stats as stats 

# Extracted Logic Modules
import etw_consumables

# --------------------------
# 1. Config & Pre-Load
# --------------------------
_TUNING = io.load_json(config.PATHS["config_tuning"])
_RAIDS = io.load_json(config.PATHS["content_raids"]) 

DIFFICULTY_SETTINGS = _TUNING.get("difficulty_settings", {})
RAID_MODIFIERS = _RAIDS.get("raid_modifiers", {})
RARITY_TUNING = _TUNING.get("rarity_tuning", {})
CATEGORY_TUNING = _TUNING.get("category_tuning", {})

def load_main_quests(): return io.load_json(config.PATHS["main_quests"], [])
def load_side_quests(): return io.load_json(config.PATHS["side_quests"])
def load_shop_items(): return io.load_json(config.PATHS["shop_items"])
def load_character_themes(): return io.load_json(config.PATHS["character_themes"], [])
def load_starter_loadouts(): return io.load_json(config.PATHS["starter_loadouts"])
def load_blueprints(): return io.load_json(config.PATHS["blueprints"], {}) # NEW

# --------------------------
# 2. Bridge Aliases
# --------------------------
def _process_game_commands(cmds):
    data = load_save_data()
    path = data.get("game_install_path", "")
    if path:
        bridge.process_game_commands(path, cmds)

def trigger_baseline_scan(save_data):
    path = save_data.get("game_install_path", "")
    if path:
        bridge.trigger_baseline_scan(path)

# --------------------------
# 3. Save Data Management
# --------------------------
def load_save_data():
    default = {
        "game_install_path": "", 
        "scrip": 0,
        "components": 0, # NEW: Meta-Currency for Crafting
        "inventory": {"sos_flare": 0, "task_reroll": 0, "lunchbox": 0},
        "tasks": [], 
        "taskboard_pool": [],
        "user_settings": { "xp_mult": 1.0, "caps_mult": 1.0, "scrip_mult": 1.0, "cost_mult": 1.0 },
        "raid_active": False,
        "raids_died": 0,
        "raids_started": 0,
        "raids_extracted": 0,
        "sos_extracts": 0,
        "consecutive_deaths": 0,
        "consecutive_extractions": 0, 
        "unlocked_task_slots": 1, 
        "unlocked_task_pool_size": 3,
        "hideout_stations": {},
        "generated_station_costs": {},
        "reputation": 0.0,
        "fortune": 0.0,
        "threat_level": 1,
        "current_extractions": [],
        "ambush_state": { "last_check_time": 0.0, "cooldown_until": 0.0, "ambushes_triggered": 0 },
        "tasks_failed": 0,
        "emergency_tasks_failed": 0,
        "active_buffs": [],
        "reward_history": [],
        "total_completed_tasks": 0,
        "easy_completed": 0,
        "medium_completed": 0,
        "hard_completed": 0,
        "emergency_completed": 0,
        "shop_unlocked": False,
        "hideout_unlocked": False,
        "medium_unlocked": False, 
        "hard_unlocked": False,   
        "current_xp": 0,
        "player_level": 1,
        "active_side_quests": [],
        "generated_side_quests": [],
        "quest_progress": {},
        "unlocked_intel": [],
        "unlocked_blueprints": [], # NEW: List of unlocked blueprint IDs/Names
        "companion_buffs": True, 
        "buffs_active": False,    
        "current_bonuses": {},    
        "baseline": {},
        "day_cycle": 1,
        "homepoint": "Megaton", 
        "insured_items": []     
    }
    
    data = io.load_json(config.PATHS["save_data"], default)
    
    for k, v in default.items():
        if k not in data: data[k] = v
        
    if not data.get("generated_station_costs"):
        etw_hideout.generate_station_costs(data)
    
    if data.get("day_cycle", 0) < 1: data["day_cycle"] = 1
    
    # NEW: Force Raid Modifier Init
    if not data.get("current_raid_modifier"):
        conf = io.load_json(config.PATHS["content_raids"])
        mods = list(conf.get("raid_modifiers", {}).keys())
        if mods:
            new_mod = random.choice(mods)
            data["current_raid_modifier"] = new_mod
            # We save immediately to persist this fix
            save_save_data(data)
    
    return data

def save_save_data(data): 
    io.save_json(config.PATHS["save_data"], data)

# --------------------------
# 4. Global State Logic
# --------------------------

def advance_game_cycle(save_data):
    cycle = save_data.get("day_cycle", 0) + 1
    save_data["day_cycle"] = cycle
    
    conf = io.load_json(config.PATHS["content_raids"])
    mods = list(conf.get("raid_modifiers", {}).keys())
    if mods:
        new_mod = random.choice(mods)
        save_data["current_raid_modifier"] = new_mod
        
    save_save_data(save_data)

# --------------------------
# 5. Item & Quest Logic
# --------------------------

def use_lunchbox(save_data):
    # Forwarding to etw_consumables.
    return etw_consumables.use_lunchbox(save_data)

def generate_companion_quest(save_data, companion_id, quest_type="recruitment"):
    params = None
    if quest_type == "recruitment": 
        params = companions.get_recruitment_quest_params(companion_id)
    elif quest_type == "loyalty": 
        params = companions.get_loyalty_quest_params(companion_id)
        
    if not params: 
        return None
        
    quest_obj = tasks.generate_companion_quest(save_data, companion_id, quest_type)
    return quest_obj

# NOTE: use_sos_flare removed. Logic migrated to etw_raid.py to prevent circular dependency.

# --------------------------
# 6. Debug Helpers
# --------------------------

def debug_increase_rep(save_data):
    save_data["easy_completed"] += 5 
    save_data["medium_completed"] += 2
    save_data["reputation"] = stats.compute_reputation(save_data)
    save_save_data(save_data)

def debug_advance_day(save_data):
    advance_game_cycle(save_data)

def debug_unlock_all_stations(save_data):
    save_data["hideout_unlocked"] = True
    save_data["shop_unlocked"] = True
    save_data["bar_unlocked"] = True
    save_save_data(save_data)

def debug_add_scrip_100(save_data):
    save_data["scrip"] += 100
    save_save_data(save_data)

def debug_level_up_companions(save_data):
    companions.add_companion_xp(save_data, 5000)
    save_save_data(save_data)

def debug_unlock_all_companions(save_data):
    roster = companions.load_companion_roster()
    if "companions" not in save_data:
        save_data["companions"] = {}
        
    for c_id in roster.keys():
        if c_id not in save_data["companions"]:
            save_data["companions"][c_id] = {}
        if not save_data["companions"][c_id].get("unlocked"):
            save_data["companions"][c_id]["unlocked"] = True
            save_data["companions"][c_id]["visible_in_bar"] = False
            save_data["companions"][c_id]["pending_slot"] = True
            if "level" not in save_data["companions"][c_id]: save_data["companions"][c_id]["level"] = 1
            if "xp" not in save_data["companions"][c_id]: save_data["companions"][c_id]["xp"] = 0
            
    save_save_data(save_data)