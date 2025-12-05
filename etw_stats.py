import math
import etw_engine as engine # Import engine for Save/Load and JSON access

# ----------------------------------------------------------------------
# 1. ECONOMY MULTIPLIERS
# ----------------------------------------------------------------------

def get_economy_mult(save_data, currency_type):
    """
    Retrieves the global multiplier for a specific currency type.
    Considers user settings and hideout buffs aggregated via engine.
    """
    settings = save_data.get("user_settings", {})
    # Use the multipliers stored in user_settings, which should be updated by Hideout/Buffs
    if currency_type == "caps": return settings.get("caps_mult", 1.0)
    if currency_type == "scrip": return settings.get("scrip_mult", 1.0)
    if currency_type == "xp": return settings.get("xp_mult", 1.0)
    if currency_type == "cost": return settings.get("cost_mult", 1.0)
    return 1.0

def apply_economy_mult(value, currency_type, save_data):
    """
    Applies the relevant economy multiplier to a base value.
    """
    mult = get_economy_mult(save_data, currency_type)
    return int(value * mult)

# ----------------------------------------------------------------------
# 2. REPUTATION & PROGRESSION
# ----------------------------------------------------------------------

def compute_reputation(save_data):
    """
    Calculates the player's reputation score (0.0 to 10.0) based on tasks completed.
    Also handles unlocking medium/hard difficulty.
    """
    easy = save_data.get("easy_completed", 0)
    med = save_data.get("medium_completed", 0)
    hard = save_data.get("hard_completed", 0)
    raids = save_data.get("raids_started", 0)
    
    # Unlock difficulty based on minimum completions
    if easy >= 3:
        save_data["medium_unlocked"] = True
    if med >= 5 or easy >= 10:
        save_data["hard_unlocked"] = True
        
    # Reputation formula based on logarithmic scaling of completions and raids
    score = (easy * 1) + (med * 3) + (hard * 6)
    val = (math.log10(1 + score) * 1.8) + (math.log10(1 + raids) * 0.25)
    
    return max(0.0, min(10.0, val))

# ----------------------------------------------------------------------
# 3. THREAT MANAGEMENT
# ----------------------------------------------------------------------

def _clamp_threat(save_data):
    """
    Ensures the threat level remains between 0 and 5.
    """
    tl = int(save_data.get("threat_level", 0) or 0)
    save_data["threat_level"] = max(0, min(5, tl)) 

def adjust_threat_on_extraction(save_data, tasks_completed, completed_difficulties):
    """
    Increases the threat level upon successful extraction.
    Bonus increase for completing hard tasks or high volume of tasks.
    """
    delta = 1 
    
    # Increase threat faster if completing Hard tasks
    if "hard" in completed_difficulties: 
        delta += 1
        
    # Increase threat if clearing many tasks at once (3+)
    if tasks_completed >= 3:
        delta += 1
        
    tl = int(save_data.get("threat_level", 0) or 0)
    
    save_data["consecutive_deaths"] = 0
    save_data["consecutive_extractions"] = save_data.get("consecutive_extractions", 0) + 1
    
    save_data["threat_level"] = tl + delta
    _clamp_threat(save_data)

def adjust_threat_on_failure(save_data):
    """
    Decreases the threat level upon death/raid failure.
    Tracks consecutive deaths.
    """
    tl = int(save_data.get("threat_level", 0) or 0)
    deaths = int(save_data.get("consecutive_deaths", 0) or 0) + 1
    tl = max(0, tl - 1)
    
    save_data["consecutive_extractions"] = 0
    save_data["threat_level"] = tl
    save_data["consecutive_deaths"] = deaths
    _clamp_threat(save_data)