import random

# Foundation
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_stats as stats
import etw_companions as companions
import etw_tasks as tasks
import etw_engine as engine # For game cycle advancement

# ----------------------------------------------------------------------
# INN / RESTING LOGIC
# ----------------------------------------------------------------------

def rest_at_inn(save_data):
    """
    Deducts scrip to advance the day, heal fatigue (conceptually), 
    and refresh daily spawns/tasks.
    """
    bar_conf = io.load_json(config.PATHS["content_bar"])
    base_cost = bar_conf.get("innkeeper", {}).get("cost_scrip", 3)
    final_cost = stats.apply_economy_mult(base_cost, "cost", save_data)

    if save_data.get("scrip", 0) < final_cost:
        return {"success": False, "msg": "Not enough Scrip to rent a room."}

    # Transaction
    save_data["scrip"] -= final_cost
    
    # Apply Buffs
    save_data["active_buffs"] = []
    new_buff = {"id": "rested_xp", "name": "Rested XP (+25%)"}
    save_data["active_buffs"].append(new_buff)

    # Progression
    engine.advance_game_cycle(save_data) 
    companions.roll_daily_bar_spawns(save_data)
    tasks.refresh_taskboard(save_data)

    io.save_json(config.PATHS["save_data"], save_data)
    return {"success": True, "msg": f"Rested for {final_cost} Scrip. All temporary fatigue cleared."}

# ----------------------------------------------------------------------
# BROKER / INTEL LOGIC
# ----------------------------------------------------------------------

def buy_raid_intel(save_data):
    """
    Purchases a random unlocked intel dossier.
    """
    intel_conf = io.load_json(config.PATHS["content_intel"])
    pool = intel_conf.get("raid_intel", [])
    known_intel = save_data.get("unlocked_intel", [])
    
    bar_conf = io.load_json(config.PATHS["content_bar"])
    base_cost = bar_conf.get("broker", {}).get("cost_scrip", 1)
    
    final_cost = stats.apply_economy_mult(base_cost, "cost", save_data)
    
    available = [i for i in pool if i["id"] not in known_intel]
    
    if not available:
        return {"success": False, "msg": "Broker has no new intel.", "sold_out": True}
        
    if save_data.get("scrip", 0) < final_cost:
        return {"success": False, "msg": "Insufficient Scrip."}
        
    save_data["scrip"] -= final_cost
    
    chosen_intel = random.choice(available)
    save_data["unlocked_intel"].append(chosen_intel["id"])
    
    io.save_json(config.PATHS["save_data"], save_data)
    
    return {"success": True, "msg": f"Acquired Dossier: {chosen_intel['title']}", "data": chosen_intel}