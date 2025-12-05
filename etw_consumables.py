import random

# Foundation Modules
import etw_config as config
import etw_io as io

# ----------------------------------------------------------------------
# CONSUMABLE ITEM LOGIC
# ----------------------------------------------------------------------

def use_lunchbox(save_data):
    """
    Consumes 1 Lunchbox to grant a random buff for the next raid.
    """
    inv = save_data.get("inventory", {})
    if inv.get("lunchbox", 0) <= 0:
        return {"success": False, "message": "No Lunchboxes in inventory."}

    possible_buffs = [
        {"id": "xp_boost", "name": "XP Boost (+25%)"},
        {"id": "caps_boost", "name": "Caps Boost (+25%)"},
        {"id": "scrip_boost", "name": "Barter (+25% Scrip)"},
        {"id": "loot_quantity", "name": "Scavenger (+1 Max Loot)"},
        {"id": "fortune_boost", "name": "Lucky (+2 Fortune)"}
    ]
    
    active_ids = [b["id"] for b in save_data.get("active_buffs", [])]
    valid_buffs = [b for b in possible_buffs if b["id"] not in active_ids]
    
    if not valid_buffs:
        return {"success": False, "message": "Max Buffs Applied!"}

    inv["lunchbox"] -= 1
    new_buff = random.choice(valid_buffs)
    
    current_buffs = save_data.get("active_buffs", [])
    current_buffs.append(new_buff)
    save_data["active_buffs"] = current_buffs
    
    io.save_json(config.PATHS["save_data"], save_data)
    return {"success": True, "message": f"Opened: {new_buff['name']}", "buff_name": new_buff['name']}