import random
import copy

# Foundation
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_stats as stats

# ----------------------------------------------------------------------
# LOADERS
# ----------------------------------------------------------------------

def _load_content_tasks():
    return io.load_json(config.PATHS["content_tasks"])

def _load_world_pool():
    return io.load_json(config.PATHS["world_pool"])

def _load_emergency_templates():
    raids = io.load_json(config.PATHS["content_raids"])
    return raids.get("emergency_task_templates", [])

def _load_difficulty_settings():
    tuning = io.load_json(config.PATHS["config_tuning"])
    return tuning.get("difficulty_settings", {})

# ----------------------------------------------------------------------
# GENERATION LOGIC
# ----------------------------------------------------------------------

def generate_task(save_data, i_offset=0, force_emergency=False, force_difficulty=None):
    """
    Generates a single, randomized task based on content pools and difficulty.
    """
    tasks_config = _load_content_tasks()
    world = _load_world_pool()
    diff_settings = _load_difficulty_settings()
    
    # 1. Determine Difficulty
    diff = "easy"
    if force_difficulty:
        diff = force_difficulty
    else:
        if save_data.get("medium_unlocked") and random.random() > 0.5: diff = "medium"
        if save_data.get("hard_unlocked") and random.random() > 0.8: diff = "hard"
    
    # 2. Determine Emergency Status
    is_emergency = False
    reward_mult = 1.0
    cycles = random.randint(2, 5) 
    flavor_text = ""
    
    if force_emergency or random.random() < 0.10: 
        is_emergency = True
        reward_mult = 1.25
        cycles = 1 
        templates = _load_emergency_templates()
        if templates: 
            flavor_text = random.choice(templates).get("description", "Priority Priority Priority")
        else: 
            flavor_text = "Priority Priority Priority"
            
    # 3. Determine Type & Tags
    t_type = random.choice(tasks_config.get("task_types", ["slay"]))
    tags = tasks_config.get("task_activity_tags", {}).get(t_type, [])[:]
    
    if is_emergency: 
        tags.append("emergency")
    
    rep = stats.compute_reputation(save_data) 
    if random.random() < (0.30 + (rep * 0.02)):
        tags.append("bonus_objective")
    
    # 4. Helpers for Objective Generation
    def get_target(pool, difficulty_bias=None):
        if not pool: return None
        valid = pool
        if difficulty_bias: 
            valid = [x for x in pool if difficulty_bias in x.get("difficulty_bias", ["easy"])]
        return random.choice(valid) if valid else random.choice(pool)

    icons_map = tasks_config.get("task_icons", {})
    colors_map = tasks_config.get("icon_colors", {})
    
    # 5. Determine Quantities
    qty_range = diff_settings.get(diff, {}).get("quantity", [3, 5])
    qty = random.randint(qty_range[0], qty_range[1])
    
    target_count = qty
    current_count = qty 
    
    objectives = []
    
    # 6. Build Main Objective
    if t_type == "slay":
        target = get_target(world.get("enemies", []), diff)
        name = target.get("name", "Enemy") if target else "Enemy"
        txt = f"Slay {qty} {name}"
        objectives.append([icons_map.get("slay"), txt, colors_map.get("slay"), current_count, target_count])
        
    elif t_type == "retrieve":
        target = get_target(world.get("items", []))
        name = target.get("name", "Item") if target else "Item"
        txt = f"Retrieve {qty} {name}"
        objectives.append([icons_map.get("retrieve"), txt, colors_map.get("retrieve"), current_count, target_count])
        
    elif t_type == "plant":
        target = get_target(world.get("locations", []), diff)
        item = get_target(world.get("items", []))
        loc_name = target.get("name", "Location") if target else "Location"
        item_name = item.get("name", "Beacon") if item else "Beacon"
        txt = f"Plant {item_name} at {loc_name}"
        objectives.append([icons_map.get("plant"), txt, colors_map.get("plant"), 1, 1])
        
    elif t_type == "clear":
        target = get_target(world.get("locations", []), diff)
        loc_name = target.get("name", "Location") if target else "Location"
        txt = f"Clear {loc_name}"
        objectives.append([icons_map.get("clear"), txt, colors_map.get("clear"), 1, 1])

    # 7. Add Complexity for Hard Difficulty
    if diff == "hard" and len(objectives) < 3:
        t2_type = random.choice(["slay", "retrieve"])
        q2 = random.randint(qty_range[0], qty_range[1])
        
        if t2_type == "slay":
            target = get_target(world.get("enemies", []), diff)
            name = target.get("name", "Enemy") if target else "Enemy"
            txt = f"Slay {q2} {name}"
            objectives.append([icons_map.get("slay"), txt, colors_map.get("slay"), q2, q2])
        else:
            target = get_target(world.get("items", []))
            name = target.get("name", "Item") if target else "Item"
            txt = f"Retrieve {q2} {name}"
            objectives.append([icons_map.get("retrieve"), txt, colors_map.get("retrieve"), q2, q2])
            
        t3_type = random.choice(["clear", "plant"])
        if t3_type == "clear":
            target = get_target(world.get("locations", []), diff)
            loc_name = target.get("name", "Location") if target else "Location"
            txt = f"Clear {loc_name}"
            objectives.append([icons_map.get("clear"), txt, colors_map.get("clear"), 1, 1])
        else:
            target = get_target(world.get("locations", []), diff)
            loc_name = target.get("name", "Location") if target else "Location"
            txt = f"Plant Beacon at {loc_name}"
            objectives.append([icons_map.get("plant"), txt, colors_map.get("plant"), 1, 1])

    # 8. Add Bonus Objective
    if "bonus_objective" in tags:
        b_type = random.choice(["slay", "retrieve"])
        b_qty = max(1, qty // 2)
        
        b_target_count = b_qty
        b_current_count = b_qty
        
        if b_type == "slay":
            target = get_target(world.get("enemies", []), diff)
            name = target.get("name", "Enemy") if target else "Enemy"
            txt = f"BONUS: Slay {b_qty} {name}"
            objectives.append([icons_map.get("slay"), txt, "#FFFFFF", b_current_count, b_target_count])
        elif b_type == "retrieve":
            target = get_target(world.get("items", []))
            name = target.get("name", "Item") if target else "Item"
            txt = f"BONUS: Retrieve {b_qty} {name}"
            objectives.append([icons_map.get("retrieve"), txt, "#FFFFFF", b_current_count, b_target_count])
            
        reward_mult += 0.5

    return {
        "task_number": i_offset,
        "name": tasks_config.get("task_title_by_type", {}).get(t_type, "Contract"),
        "difficulty": diff,
        "objectives": objectives,
        "original_objectives": copy.deepcopy(objectives), 
        "state": "pending",
        "reward_mult": reward_mult,
        "tags": tags,
        "is_emergency": is_emergency,
        "flavor_text": flavor_text,
        "cycles_remaining": cycles,
        "ready_to_complete": False
    }