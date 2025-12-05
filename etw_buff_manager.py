import etw_bridge as bridge
import etw_buffs as buffs
import etw_config as config
import etw_io as io

# ----------------------------------------------------------------------
# STAT MAPPING CONSTANTS
# ----------------------------------------------------------------------
STAT_MAP = {
    # --- DERIVED STATS ---
    "hp": ("health", 200),
    "ap": ("actionpoints", 85),
    "carry_weight": ("carryweight", 150),
    "defense": ("damageresist", 0),  
    "move_speed": ("speedmult", 100), 

    # --- SPECIAL ---
    "strength": ("strength", 5),
    "perception": ("perception", 5),
    "endurance": ("endurance", 5),
    "charisma": ("charisma", 5),
    "intelligence": ("intelligence", 5),
    "agility": ("agility", 5),
    "luck": ("luck", 5),

    # --- SKILLS ---
    "barter": ("barter", 15),
    "bigguns": ("bigguns", 15),
    "energyweapons": ("energyweapons", 15),
    "explosives": ("explosives", 15),
    "lockpick": ("lockpick", 15),
    "medicine": ("medicine", 15),
    "meleeweapons": ("meleeweapons", 15),
    "repair": ("repair", 15),
    "science": ("science", 15),
    "smallguns": ("smallguns", 15),
    "sneak": ("sneak", 15),
    "speech": ("speech", 15),
    "unarmed": ("unarmed", 15)
}

# ----------------------------------------------------------------------
# BUFF APPLICATION
# ----------------------------------------------------------------------

def apply_companion_buffs(save_data):
    """
    Calculates active companion bonuses and applies them via console commands.
    """
    if save_data.get("buffs_active", False): 
        return 
    
    bonuses = buffs.calculate_companion_bonuses(save_data)
    baseline = save_data.get("baseline", {})
    
    applied_deltas = {}
    cmds = []
    
    for bonus_key, (av_name, default_val) in STAT_MAP.items():
        mult = bonuses.get(bonus_key, 1.0)
        
        if mult <= 1.0 and bonus_key not in bonuses: 
            continue
            
        delta = 0
        
        if bonus_key in ["hp", "ap", "carry_weight"]:
            base_val = baseline.get(av_name, default_val)
            delta = int(base_val * (mult - 1.0))
            
        elif bonus_key == "defense":
            delta = int(100 * (mult - 1.0))
            
        elif bonus_key == "move_speed":
            delta = int(100 * (mult - 1.0))
            
        else:
            if mult > 1.0:
                base_val = baseline.get(av_name, default_val)
                delta = int(base_val * (mult - 1.0))
            
        if delta > 0:
            cmds.append(f"player.modav {av_name} {delta}")
            applied_deltas[av_name] = delta

    if cmds:
        game_path = save_data.get("game_install_path", "")
        if game_path:
            bridge.process_game_commands(game_path, cmds)
            
            save_data["buffs_active"] = True
            save_data["current_bonuses"] = applied_deltas
            io.save_json(config.PATHS["save_data"], save_data)

# ----------------------------------------------------------------------
# BUFF REMOVAL
# ----------------------------------------------------------------------

def remove_companion_buffs(save_data):
    """
    Reverses the buffs applied in apply_companion_buffs.
    """
    if not save_data.get("buffs_active", False): 
        return
    
    current_bonuses = save_data.get("current_bonuses", {})
    if not current_bonuses: 
        save_data["buffs_active"] = False
        io.save_json(config.PATHS["save_data"], save_data)
        return
    
    cmds = []
    for stat, amount in current_bonuses.items():
        cmds.append(f"player.modav {stat} {int(-amount)}")
        
    game_path = save_data.get("game_install_path", "")
    if game_path:
        bridge.process_game_commands(game_path, cmds)
        
    save_data["buffs_active"] = False
    save_data["current_bonuses"] = {}
    io.save_json(config.PATHS["save_data"], save_data)