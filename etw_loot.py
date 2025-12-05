import random
import datetime

# Foundation Modules
import etw_config as config
import etw_io as io

# Logic Modules
import etw_buffs as buffs 
import etw_stats as stats 

# ----------------------------------------------------------------------
# GLOBAL LOOT CACHE
# ----------------------------------------------------------------------
_INDEXED_LOOT = {"all": [], "by_category": {}, "by_rarity": {}} 

def get_loot_pool_cached():
    """
    Loads and indexes all loot files (weapons, armor, etc.) into a unified structure.
    Returns the global cache.
    """
    if not _INDEXED_LOOT["all"]:
        # Refactored to use IO/Config
        weapons = io.load_json(config.PATHS["weapons"], [])
        armor = io.load_json(config.PATHS["armor"], [])
        consumables = io.load_json(config.PATHS["consumables"], [])
        ammo = io.load_json(config.PATHS["ammo"], [])
        misc = io.load_json(config.PATHS["misc"], [])
        
        all_items = weapons + armor + consumables + ammo + misc
        _INDEXED_LOOT["all"] = all_items
        
        for item in all_items:
            cat = item.get("category", "misc")
            rar = item.get("rarity", "tier_1")
            
            if cat not in _INDEXED_LOOT["by_category"]: 
                _INDEXED_LOOT["by_category"][cat] = []
            _INDEXED_LOOT["by_category"][cat].append(item)
            
            if rar not in _INDEXED_LOOT["by_rarity"]: 
                _INDEXED_LOOT["by_rarity"][rar] = []
            _INDEXED_LOOT["by_rarity"][rar].append(item)
            
    return _INDEXED_LOOT

# ----------------------------------------------------------------------
# SELECTION LOGIC
# ----------------------------------------------------------------------

def _choose_item_category(rep, fortune):
    """
    Weighted selection of item category based on Reputation and Fortune.
    High Rep -> More Weapons/Armor. High Fortune -> More Misc/Valuables.
    """
    weights = {"consumable": 40, "ammo": 30, "weapon": 10, "armor": 10, "misc": 10}
    
    # Reputation Tilt (favor combat gear)
    tilt = rep * 1.5
    weights["weapon"] += tilt
    weights["armor"] += tilt
    
    # Balance reduction
    weights["consumable"] = max(5, weights["consumable"] - tilt)
    weights["ammo"] = max(5, weights["ammo"] - tilt)
    
    # Fortune Tilt (favor misc/valuables)
    weights["misc"] += (fortune * 1.0)
    
    cats = list(weights.keys())
    vals = [weights[k] for k in cats]
    
    return random.choices(cats, weights=vals, k=1)[0]

def _choose_item_rarity(rep, fortune, difficulty="easy"):
    """
    Weighted selection of Rarity Tier (1-4).
    Heavily influenced by Difficulty, Reputation, and Fortune.
    """
    # Base weights
    w = {"tier_1": 100, "tier_2": 5, "tier_3": 0, "tier_4": 0}
    
    # Difficulty Overrides
    if difficulty == "medium":
        w["tier_1"] = 80; w["tier_2"] = 30; w["tier_3"] = 5
    elif difficulty == "hard":
        w["tier_1"] = 50; w["tier_2"] = 60; w["tier_3"] = 20; w["tier_4"] = 2
        
    # Reputation Scaling
    w["tier_2"] += (rep * 10)
    w["tier_3"] += (rep * 5)
    if rep > 5: 
        w["tier_4"] += (rep - 5) * 2
        
    # Fortune Scaling
    w["tier_2"] += (fortune * 3)
    w["tier_3"] += (fortune * 1.5)
    w["tier_4"] += (fortune * 0.5)
    
    # Normalization (Reduce common if high tier chances are high)
    total_high_tier_weight = w["tier_2"] + w["tier_3"] + w["tier_4"]
    w["tier_1"] = max(10, w["tier_1"] - (total_high_tier_weight * 0.2))
    
    tiers = list(w.keys())
    vals = [w[k] for k in tiers]
    
    return random.choices(tiers, weights=vals, k=1)[0]

# ----------------------------------------------------------------------
# REWARD CALCULATORS
# ----------------------------------------------------------------------

def calculate_reward_package(source_type, difficulty, save_data, duration=0):
    """
    Generates a full reward bundle (XP, Caps, Scrip, Items) based on context.
    """
    pool_data = get_loot_pool_cached()
    mods = buffs.get_player_modifiers(save_data)
    rep = stats.compute_reputation(save_data)
    fortune = mods["effective_fortune"]
    
    # --- MODIFIER CHECK: Fortune's Bounty ---
    current_mod = save_data.get("current_raid_modifier")
    if current_mod == "fortunes_bounty" and source_type == "raid":
        fortune += 5.0
        mods["scrip_mult"] += 0.5 

    # Base Values per Difficulty
    base_caps = 100; base_scrip = 1; base_xp = 100 
    if difficulty == "medium": 
        base_caps = 300; base_scrip = 3; base_xp = 300
    elif difficulty == "hard": 
        base_caps = 600; base_scrip = 6; base_xp = 600
        
    # Multipliers
    user_settings = save_data.get("user_settings", {})
    global_xp = user_settings.get("xp_mult", 1.0)
    global_caps = user_settings.get("caps_mult", 1.0)
    global_scrip = user_settings.get("scrip_mult", 1.0)
    
    caps_mult = mods["caps_mult"] * global_caps + (fortune * 0.01)
    xp_mult = mods["xp_mult"] * global_xp
    scrip_mult = mods["scrip_mult"] * global_scrip
    
    final_caps = int(base_caps * caps_mult)
    final_scrip = int(base_scrip * scrip_mult)
    final_xp = int(base_xp * xp_mult)
    
    # Item Generation
    items = []
    base_items = 1
    if difficulty == "medium": base_items = 2
    if difficulty == "hard": base_items = 3
    
    total_items = base_items + mods["loot_count_bonus"]
    if rep >= 8: total_items += 1
    
    # Companion Bonus Loot Roll
    c_bonuses = buffs.calculate_companion_bonuses(save_data) 
    if c_bonuses["loot"] > 1.0:
        if random.random() < (c_bonuses["loot"] - 1.0): 
            total_items += 1

    for _ in range(total_items):
        cat = _choose_item_category(rep, fortune)
        tier = _choose_item_rarity(rep, fortune, difficulty)
        
        candidates = [i for i in pool_data["all"] if i.get("category") == cat and i.get("rarity") == tier]
        if not candidates: 
            candidates = [i for i in pool_data["all"] if i.get("category") == cat]
            
        if candidates:
            item = random.choice(candidates)
            base_qty = 1
            if cat == "ammo": base_qty = random.randint(20, 50)
            elif cat == "consumable": base_qty = random.randint(1, 2)
            
            # Quantity Multipliers
            q_mult = 1.0 + (rep * 0.1) + (fortune * 0.05)
            if difficulty == "medium": q_mult += 0.2
            if difficulty == "hard": q_mult += 0.5
            
            final_qty = max(1, int(base_qty * q_mult))
            
            items.append({
                "code": item.get("code", ""), 
                "name": item.get("name", "Unknown"), 
                "qty": final_qty
            })

    # Raid Modifier Bonus Item
    if current_mod and source_type == "raid":
        chance = 1.0 if current_mod == "fortunes_bounty" else 0.5
        
        if random.random() < chance:
            tier = _choose_item_rarity(rep, fortune + 5.0, difficulty) 
            pool = pool_data["all"]
            candidates = [i for i in pool if i.get("rarity") == tier]
            if candidates:
                bonus_item = random.choice(candidates)
                items.append({
                    "code": bonus_item.get("code", ""), 
                    "name": bonus_item.get("name", "Bonus Item"), 
                    "qty": 1,
                    "from_modifier": True 
                })
                
    return {
        "xp": final_xp, 
        "caps": final_caps, 
        "scrip": final_scrip, 
        "items": items
    }

def calculate_extraction_reward(duration, save_data):
    """
    Calculates rewards specifically for the Raid Time (Survival Bonus).
    """
    duration_min = duration / 60.0
    
    # Thresholds
    MIN_TIME = 10.0; MAX_TIME = 45.0
    R_SCRIP = (1, 3); R_CAPS = (50, 150); R_XP = (100, 300)
    
    if duration_min < MIN_TIME: factor = 0.0
    elif duration_min >= MAX_TIME: factor = 1.0
    else: factor = (duration_min - MIN_TIME) / (MAX_TIME - MIN_TIME)
        
    base_scrip = int(R_SCRIP[0] + (R_SCRIP[1] - R_SCRIP[0]) * factor)
    base_caps  = int(R_CAPS[0]  + (R_CAPS[1]  - R_CAPS[0])  * factor)
    base_xp    = int(R_XP[0]    + (R_XP[1]    - R_XP[0])    * factor)
    
    mods = buffs.get_player_modifiers(save_data) 
    user_settings = save_data.get("user_settings", {})
    
    xp_mult = mods["xp_mult"] * user_settings.get("xp_mult", 1.0)
    caps_mult = mods["caps_mult"] * user_settings.get("caps_mult", 1.0) + (mods["effective_fortune"] * 0.01)
    scrip_mult = mods["scrip_mult"] * user_settings.get("scrip_mult", 1.0)
    
    return {
        "xp": int(base_xp * xp_mult), 
        "caps": int(base_caps * caps_mult), 
        "scrip": int(base_scrip * scrip_mult), 
        "items": []
    }

def log_reward_history(save_data, source, pkg):
    """
    Logs the acquisition to the history buffer for UI display.
    """
    if "reward_history" not in save_data:
        save_data["reward_history"] = []
        
    entry = {
        "source": source,
        "time": datetime.datetime.now().strftime("%H:%M"),
        "xp": pkg.get("xp", 0),
        "caps": pkg.get("caps", 0),
        "scrip": pkg.get("scrip", 0),
        "items": pkg.get("items", [])
    }
    
    save_data["reward_history"].append(entry)
    
    # Cap history size
    if len(save_data["reward_history"]) > 50:
        save_data["reward_history"] = save_data["reward_history"][-50:]