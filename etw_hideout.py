import random
import math

# Foundation
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_engine as engine 
import etw_loot as loot 
import etw_buffs as buffs_logic
import etw_inventory as inventory # Needed for Dismantle verification

# ----------------------------------------------------------------------
# HIDEOUT LOGIC
# ----------------------------------------------------------------------

def generate_station_costs(save_data):
    # Ensure cache is loaded
    loot.get_loot_pool_cached()
    
    content = io.load_json(config.PATHS["content_hideout"])
    stations_config = content.get("stations", [])
    
    all_stations_costs = {}
    
    for s_conf in stations_config:
        s_id = s_conf["id"]
        station_levels = {}
        
        cost_theme_tags = []
        if "press" in s_id or "workbench" in s_id: 
            cost_theme_tags = ["tech", "tool", "component"]
        elif "kitchen" in s_id: 
            cost_theme_tags = ["misc", "food", "junk"]
        elif "chem" in s_id: 
            cost_theme_tags = ["tech", "medical", "chemicals"]
        elif "supply" in s_id: 
            cost_theme_tags = ["storage", "misc"]
        elif "lounge" in s_id or "bobble" in s_id or "tree" in s_id: 
            cost_theme_tags = ["valuable", "misc"]
        else: 
            cost_theme_tags = ["misc", "junk"]

        for lvl_conf in s_conf.get("levels", []):
            level = lvl_conf["level"]
            cost_items = []
            
            num_reqs = 1
            if level >= 3: num_reqs = 2
            
            for _ in range(num_reqs):
                tag = random.choice(cost_theme_tags)
                
                target_rarity = "tier_1"
                if level >= 3: target_rarity = "tier_2"
                if level == 5: target_rarity = "tier_3"
                
                pool = loot.get_loot_pool_cached()["all"]
                
                candidates = [i for i in pool if tag in i.get("tags", []) or i.get("tag") == tag or i.get("category") == tag]
                tier_candidates = [i for i in candidates if i.get("rarity") == target_rarity]
                
                final_pool = tier_candidates if tier_candidates else candidates
                if not final_pool: 
                    final_pool = [i for i in pool if i.get("rarity") == "tier_1"]
                
                if final_pool:
                    item = random.choice(final_pool)
                    base_qty = random.randint(2, 5)
                    qty_mult = 1.0 + (level * 0.5)
                    final_qty = int(base_qty * qty_mult)
                    
                    if not any(x['code'] == item['code'] for x in cost_items):
                        cost_items.append({
                            "code": item.get("code"),
                            "name": item.get("name"),
                            "qty": final_qty
                        })

            station_levels[str(level)] = {
                "cost_items": cost_items
            }
            
        all_stations_costs[s_id] = station_levels
        
    save_data["generated_station_costs"] = all_stations_costs
    io.save_json(config.PATHS["save_data"], save_data)
    return all_stations_costs

def update_hideout_timers(save_data, elapsed_minutes):
    """
    Advances progress for ALL stations (Passive & Active).
    """
    stations = save_data.get("hideout_stations", {})
    content = io.load_json(config.PATHS["content_hideout"])
    config_map = {s["id"]: s for s in content.get("stations", [])}
    
    for s_id, data in stations.items():
        level = data.get("level", 0)
        if level < 1: continue
        
        s_conf = config_map.get(s_id)
        if not s_conf: continue
        
        lvl_conf = next((l for l in s_conf["levels"] if l["level"] == level), None)
        if not lvl_conf: continue
        
        # TYPE 1: PASSIVE PRODUCTION
        if s_conf.get("type") == "passive_production":
            storage = data.get("storage", 0)
            cap = math.ceil(level / 2.0)
            
            if storage >= cap: continue 
            
            rate = lvl_conf.get("production_rate", 60)
            progress = data.get("progress", 0.0)
            progress += elapsed_minutes
            
            while progress >= rate:
                if storage < cap:
                    storage += 1
                    progress -= rate
                    data["storage"] = storage
                    if storage >= cap:
                        progress = 0.0 
                        break
                else:
                    progress = 0.0
                    break
            data["progress"] = progress

        # TYPE 2: ACTIVE CRAFTING (Generic + Workbench)
        elif s_conf.get("type") == "active_crafting":
            if "active_slots" not in data: data["active_slots"] = []
            
            cap = math.ceil(level / 2.0)
            storage = data.get("storage", 0)
            
            slots = data.get("active_slots", [])
            
            for slot in slots:
                if not slot or not slot.get("code"): continue
                if storage >= cap: break 
                
                # Standardize rate: Check if slot has specific time override (e.g. huge craft)
                # For now, use station speed
                req_time = lvl_conf.get("production_rate", 60)
                slot["progress"] += elapsed_minutes
                
                while slot["progress"] >= req_time:
                    if storage < cap:
                        if "finished_items" not in data: data["finished_items"] = []
                        
                        # Store the result type (item vs currency)
                        data["finished_items"].append({
                            "code": slot["code"],
                            "name": slot["name"],
                            "base_qty": slot.get("base_qty", 1),
                            "result_type": slot.get("result_type", "item") # Default to item
                        })
                        
                        storage += 1
                        data["storage"] = storage
                        
                        # Clear slot logic: set to None/Empty dict? 
                        # Logic below relied on overwriting.
                        # We need to clear THIS specific slot instance in the list?
                        # The update logic for slots is complex if we modify list while iterating.
                        # BUT here we are just calculating "did it finish?".
                        # If finished, we effectively 'consume' the job time.
                        
                        # FIX: We need to MARK it as done or remove it?
                        # The UI typically displays slots. If a slot finishes, it becomes empty.
                        # But we are inside a loop over 'slots'.
                        # The previous logic was: "slot['progress'] = 0.0" if blocked, or "break" if done?
                        # Actually, previous logic was missing the "Remove from active_slots" step.
                        # It seemed to assume the slot stays "Busy" until collected?
                        # No, the previous code had `slot["progress"] -= req_time` if looping?
                        # Wait, if it finishes, it moves to 'finished_items' storage.
                        # So the SLOT should become free immediately.
                        
                        # Let's clear the slot data in place
                        slot.clear() # Empties the dict, making it "Idle"
                        slot["progress"] = 0.0 # Reset just in case
                        
                        # Since slot is now empty, we stop processing THIS slot's time
                        break 
                    else:
                        slot["progress"] = req_time # Cap at max if storage full
                        break

    io.save_json(config.PATHS["save_data"], save_data)

# ----------------------------------------------------------------------
# JOB INITIATORS
# ----------------------------------------------------------------------

def _get_free_slot_index(save_data, station_id, max_slots):
    stations = save_data.get("hideout_stations", {})
    data = stations.get(station_id)
    if "active_slots" not in data: data["active_slots"] = []
    slots = data["active_slots"]
    
    for i in range(len(slots)):
        if not slots[i] or not slots[i].get("code"):
            return i
            
    if len(slots) < max_slots:
        slots.append({})
        return len(slots) - 1
        
    return -1

def start_crafting_job(save_data, station_id, recipe_code, recipe_name, base_qty=1):
    """
    Legacy wrapper for standard crafting (producing items).
    """
    return _start_job_internal(save_data, station_id, recipe_code, recipe_name, base_qty, "item")

def start_dismantle_job(save_data, station_id, item_code, item_name, yield_amount):
    """
    Starts a job that converts an item into Components (Currency).
    """
    # 1. Verify & Remove Item
    req_item = {"code": item_code, "qty": 1, "name": item_name}
    result = inventory.verify_and_remove_items(save_data, [req_item])
    
    if not result["success"]:
        return False, f"Missing: {item_name}"
        
    # 2. Start Job (Code = "COMPONENTS", Qty = Yield)
    success, msg = _start_job_internal(save_data, station_id, "COMPONENTS", f"Dismantle: {item_name}", yield_amount, "currency")
    
    if not success:
        # CRITICAL: Refund item if job failed to start (e.g. full slots)
        # Note: Since verify_and_remove removed it, we must add it back.
        engine._process_game_commands([f"player.additem {item_code} 1"])
        inventory.update_local_inventory(save_data, added_items=[{"code": item_code, "qty": 1}])
        return False, msg
        
    return True, "Dismantling started."

def start_blueprint_craft_job(save_data, station_id, blueprint):
    """
    Starts a job to craft a Blueprint item. Consumes Components.
    """
    cost = blueprint.get("components_cost", 0)
    
    # 1. Check Currency
    if save_data.get("components", 0) < cost:
        return False, "Insufficient Components."
        
    # 2. Check Slots BEFORE debiting currency
    # Need to fetch max slots logic
    content = io.load_json(config.PATHS["content_hideout"])
    s_conf = next((s for s in content["stations"] if s["id"] == station_id), None)
    stations = save_data.get("hideout_stations", {})
    data = stations.get(station_id, {})
    level = data.get("level", 1)
    lvl_conf = next((l for l in s_conf["levels"] if l["level"] == level), None)
    max_slots = lvl_conf.get("slots", 1)
    
    if _get_free_slot_index(save_data, station_id, max_slots) == -1:
        return False, "All slots busy."
        
    # 3. Debit Currency
    save_data["components"] -= cost
    
    # 4. Start Job
    code = blueprint["code"]
    name = blueprint["name"]
    success, msg = _start_job_internal(save_data, station_id, code, name, 1, "item")
    
    if not success:
        # Refund on failure
        save_data["components"] += cost
        io.save_json(config.PATHS["save_data"], save_data)
        return False, msg
        
    io.save_json(config.PATHS["save_data"], save_data)
    return True, f"Crafting {name}..."

def _start_job_internal(save_data, station_id, code, name, qty, result_type):
    stations = save_data.get("hideout_stations", {})
    data = stations.get(station_id)
    if not data: return False, "Station locked."
    
    content = io.load_json(config.PATHS["content_hideout"])
    s_conf = next((s for s in content.get("stations", []) if s["id"] == station_id), None)
    level = data.get("level", 1)
    lvl_conf = next((l for l in s_conf["levels"] if l["level"] == level), None)
    max_slots = lvl_conf.get("slots", 1)
    
    idx = _get_free_slot_index(save_data, station_id, max_slots)
    
    if idx == -1: return False, "All slots busy."
    
    slots = data["active_slots"]
    slots[idx] = {
        "code": code,
        "name": name,
        "base_qty": qty,
        "progress": 0.0,
        "result_type": result_type
    }
    
    io.save_json(config.PATHS["save_data"], save_data)
    return True, f"Job started in Slot {idx + 1}"

# ----------------------------------------------------------------------
# COLLECTION
# ----------------------------------------------------------------------

def collect_finished_craft(save_data, station_id):
    """
    Collects ONE batch from the finished queue.
    Handles both Items and Currency (Components).
    """
    data = save_data.get("hideout_stations", {}).get(station_id)
    if not data: return {"success": False, "msg": "Error"}
    
    finished = data.get("finished_items", [])
    if not finished: return {"success": False, "msg": "Storage empty"}
    
    item_batch = finished.pop(0)
    data["finished_items"] = finished
    data["storage"] = max(0, data.get("storage", 0) - 1)
    
    qty = item_batch.get("base_qty", 1)
    res_type = item_batch.get("result_type", "item")
    name = item_batch.get("name", "Unknown")
    
    msg = ""
    
    if res_type == "currency":
        # Components
        save_data["components"] = save_data.get("components", 0) + qty
        msg = f"Salvaged: {qty} Components"
    else:
        # In-Game Item
        code = item_batch["code"]
        engine._process_game_commands([f"player.additem {code} {qty}"])
        # Update local JSON
        inventory.update_local_inventory(save_data, added_items=[{"code": code, "qty": qty, "name": name}])
        msg = f"Collected: {name}"
        
    io.save_json(config.PATHS["save_data"], save_data)
    return {"success": True, "msg": msg}

def cancel_crafting_job(save_data, station_id, slot_index):
    """
    Cancels the job. 
    NOTE: Does not currently refund components/items to prevent exploit/complexity.
    Or should we? For now, standard behavior: Cancel = Loss.
    """
    stations = save_data.get("hideout_stations", {})
    data = stations.get(station_id)
    if not data: return {"success": False, "msg": "Station error"}
    
    slots = data.get("active_slots", [])
    if slot_index < 0 or slot_index >= len(slots):
        return {"success": False, "msg": "Invalid slot"}
        
    slots[slot_index] = {} 
    
    io.save_json(config.PATHS["save_data"], save_data)
    return {"success": True, "msg": "Job Cancelled"}

# ----------------------------------------------------------------------
# PASSIVE CLAIM (Existing)
# ----------------------------------------------------------------------

def claim_production(save_data, station_id):
    """
    Collects items from a PASSIVE station's storage.
    """
    data = save_data.get("hideout_stations", {}).get(station_id)
    if not data: return {"success": False, "msg": "Station not found"}
    
    storage = data.get("storage", 0)
    if storage <= 0: return {"success": False, "msg": "Storage empty"}
    
    content = io.load_json(config.PATHS["content_hideout"])
    s_conf = next((s for s in content.get("stations", []) if s["id"] == station_id), None)
    level = data.get("level", 1)
    lvl_conf = next((l for l in s_conf["levels"] if l["level"] == level), None)
    output = lvl_conf.get("output", {})
    
    reward_msg = ""
    cmds = []
    total_cycles = storage
    out_type = output.get("type")
    
    if out_type == "scrip":
        base_qty = output.get("qty", 0)
        amount = base_qty * total_cycles
        save_data["scrip"] += amount
        reward_msg = f"Collected {amount} Scrip"
        
    elif out_type == "caps":
        base_qty = output.get("qty", 0)
        amount = base_qty * total_cycles
        cmds.append(f"player.additem 0000000F {amount}")
        reward_msg = f"Collected {amount} Caps"
        
    elif out_type == "random_loot":
        mods = buffs_logic.get_player_modifiers(save_data)
        fortune = save_data.get("fortune", 0.0) + mods["effective_fortune"]
        
        items_gained = []
        items_per_cycle = output.get("count", 1)
        total_items = items_per_cycle * total_cycles
        pool = loot.get_loot_pool_cached()
        
        for _ in range(total_items):
            # Note: accessing internal method via public import context
            tier = loot._choose_item_rarity(0, fortune) 
            candidates = [i for i in pool["all"] if i.get("rarity") == tier]
            if not candidates: candidates = pool["all"]
            item = random.choice(candidates)
            items_gained.append(f"{item['name']}")
            cmds.append(f"player.additem {item['code']} 1")
        reward_msg = f"Looted: {len(items_gained)} Items"

    data["storage"] = 0
    io.save_json(config.PATHS["save_data"], save_data)
    engine._process_game_commands(cmds)
    
    return {"success": True, "msg": reward_msg}

def check_station_requirements(station_id, level, save_data):
    content = io.load_json(config.PATHS["content_hideout"])
    s_conf = next((s for s in content.get("stations", []) if s["id"] == station_id), None)
    
    if not s_conf: return False, "Unknown Station"
    
    req = s_conf.get("requirement")
    if not req: return True, "OK"
    
    req_id = req.get("station_id")
    req_target_lvl = level 
    
    user_stations = save_data.get("hideout_stations", {})
    target_data = user_stations.get(req_id, {})
    current_lvl = target_data.get("level", 0)
    
    if current_lvl < req_target_lvl:
        req_conf = next((s for s in content.get("stations", []) if s["id"] == req_id), None)
        req_name = req_conf["name"] if req_conf else req_id
        return False, f"Requires {req_name} Lvl {req_target_lvl}"
        
    return True, "OK"

# ----------------------------------------------------------------------
# WORKBENCH HELPERS
# ----------------------------------------------------------------------

def get_workbench_data(save_data, station_level):
    """
    Returns (dismantle_list, craft_list) based on station level and inventory.
    """
    # 1. Load Blueprint DB
    bp_db = io.load_json(config.PATHS["blueprints"], {})
    
    # 2. Build Dismantle List
    # Filter 'components' list by station level (Lvl 1=1 component, Lvl 4=4 components)
    # The logic: Lvl 1 station can process 1-yield items. Lvl 4 can process 1,2,3,4 yields.
    
    max_yield = station_level if station_level <= 4 else 4
    all_comps = bp_db.get("components", [])
    valid_comps = [c for c in all_comps if c.get("components_yield", 1) <= max_yield]
    
    # Check Player Inventory
    game_path = save_data.get("game_install_path", "")
    char_data = inventory.get_character_data(game_path)
    current_inv = char_data.get("inventory", [])
    
    dismantle_options = []
    
    for comp_def in valid_comps:
        code = comp_def["code"]
        suffix = code[-6:] if len(code) >= 6 else code
        
        # Find in inventory
        found_qty = 0
        for inv_item in current_inv:
            inv_code = inv_item.get("code", "")
            inv_suffix = inv_code[-6:] if len(inv_code) >= 6 else inv_code
            if inv_code == code or inv_suffix == suffix:
                found_qty += inv_item.get("qty", 0)
                
        if found_qty > 0:
            dismantle_options.append({
                "name": comp_def["name"],
                "code": code,
                "yield": comp_def["components_yield"],
                "owned": found_qty
            })
            
    # 3. Build Craft List
    # Filter 'blueprints' list by station level
    all_bps = bp_db.get("blueprints", [])
    valid_bps = [b for b in all_bps if b.get("station_level_required", 1) <= station_level]
    
    # Check Unlock Status
    unlocked_ids = save_data.get("unlocked_blueprints", [])
    
    craft_options = []
    for bp in valid_bps:
        # We can key unlock status by Code or Name. JSON has "unlocked": false which is static.
        # We check the save_data list.
        # Assuming ID is 'code' for uniqueness.
        is_unlocked = bp["code"] in unlocked_ids
        
        craft_options.append({
            "name": bp["name"],
            "code": bp["code"],
            "cost": bp["components_cost"],
            "unlocked": is_unlocked,
            "raw": bp
        })
        
    return dismantle_options, craft_options