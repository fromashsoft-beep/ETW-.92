import copy

# Foundation Modules
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_companions as companions
import etw_task_generator as generator
import etw_loot as loot
import etw_stats as stats
import etw_bridge as bridge

# ----------------------------------------------------------------------
# BOARD MANAGEMENT
# ----------------------------------------------------------------------

def refresh_taskboard(save_data):
    """
    Updates the task board pool, removing aged tasks and generating new ones.
    """
    pool = save_data.get("taskboard_pool", [])
    # 1. Remove expired tasks
    pool = [t for t in pool if t.get("cycles_remaining", 1) > 0] 
    
    # 2. Determine target count based on unlocks
    target_count = min(8, save_data.get("unlocked_task_pool_size", 3))
    
    # 3. Calculate next ID
    all_ids = [t.get("task_number", 0) for t in save_data.get("tasks", [])] + \
              [t.get("task_number", 0) for t in save_data.get("taskboard_pool", [])]
    next_id = (max(all_ids) + 1) if all_ids else 1
    
    # 4. Fill pool
    while len(pool) < target_count:
        new_task = generator.generate_task(save_data, next_id)
        pool.append(new_task)
        next_id += 1
        
    save_data["taskboard_pool"] = pool
    io.save_json(config.PATHS["save_data"], save_data)

def accept_task_from_board(task_number, save_data):
    """
    Moves a task from the Board Pool to the Active Log.
    """
    active_tasks = [t for t in save_data.get("tasks", []) if t.get("state") == "pending"]
    cap = save_data.get("unlocked_task_slots", 1)
    
    if len(active_tasks) >= cap: 
        return {"success": False, "message": "Quest Log Full"}
    
    pool = save_data.get("taskboard_pool", [])
    target_task = next((t for t in pool if t["task_number"] == task_number), None)
    
    if not target_task: 
        return {"success": False, "message": "Task not found."}
    
    pool.remove(target_task)
    save_data["tasks"].append(target_task)
    save_data["taskboard_pool"] = pool
    io.save_json(config.PATHS["save_data"], save_data)
    
    return {"success": True, "message": "Contract Accepted"}

def reroll_task_on_board(task_number, save_data):
    """
    Consumes a Reroll Token to replace a specific task on the board.
    """
    inv = save_data.get("inventory", {})
    if inv.get("task_reroll", 0) <= 0: return False
    
    pool = save_data.get("taskboard_pool", [])
    target_task = next((t for t in pool if t["task_number"] == task_number), None)
    
    # Cannot reroll Emergency tasks
    if not target_task or target_task.get("is_emergency"): return False
    
    # Consume item
    inv["task_reroll"] -= 1
    
    # Generate replacement
    new_task = generator.generate_task(save_data, task_number)
    
    # Replace in place to maintain order
    idx = pool.index(target_task)
    pool[idx] = new_task
    
    io.save_json(config.PATHS["save_data"], save_data)
    return True

# ----------------------------------------------------------------------
# UPGRADE COSTS
# ----------------------------------------------------------------------

def get_next_slot_cost(save_data):
    current = save_data.get("unlocked_task_slots", 1)
    if current >= 5: return None
    costs = [10, 15, 15, 20, 20]
    return costs[current] if current < len(costs) else 20

def get_next_pool_cost(save_data):
    current = save_data.get("unlocked_task_pool_size", 3)
    if current >= 8: return None
    idx = current - 3
    costs = [5, 10, 10, 15, 20]
    return costs[idx] if 0 <= idx < len(costs) else 20

# ----------------------------------------------------------------------
# LIFECYCLE MANAGEMENT
# ----------------------------------------------------------------------

def _age_tasks(save_data):
    """
    Decays 'cycles_remaining' on all active and board tasks.
    """
    # Age Active Tasks
    active_tasks = save_data.get("tasks", [])
    surviving_tasks = []
    
    for t in active_tasks:
        t["cycles_remaining"] = t.get("cycles_remaining", 2) - 1
        
        if t["cycles_remaining"] <= 0:
            save_data["tasks_failed"] += 1
            if t.get("is_emergency"): 
                save_data["emergency_tasks_failed"] += 1
            continue 
            
        surviving_tasks.append(t)
        
    save_data["tasks"] = surviving_tasks
    
    # Age Board Tasks
    pool = save_data.get("taskboard_pool", [])
    valid_pool = [t for t in pool if t.get("cycles_remaining", 2) - 1 > 0]
    
    for t in valid_pool: 
        t["cycles_remaining"] -= 1
        
    save_data["taskboard_pool"] = valid_pool

def generate_companion_quest(save_data, companion_id, quest_type="recruitment"):
    """
    Generates a dynamic side quest using the Generator.
    """
    params = None
    difficulty_override = None 
    
    if quest_type == "recruitment": 
        params = companions.get_recruitment_quest_params(companion_id)
        difficulty_override = "medium"
    elif quest_type == "loyalty": 
        params = companions.get_loyalty_quest_params(companion_id)
        difficulty_override = "hard"
    
    if not params: return None
    
    target_task = None
    
    for _ in range(15): 
        t = generator.generate_task(save_data, force_difficulty=difficulty_override)
        if t["difficulty"] == difficulty_override:
            if quest_type == "loyalty" and len(t["objectives"]) < 3:
                continue 
            target_task = t; break
            
    if not target_task: 
        target_task = generator.generate_task(save_data, force_difficulty=difficulty_override) 
    
    objectives_list = []
    for obj in target_task["objectives"]: 
        objectives_list.append(obj[1]) 
        
    q_id = f"{quest_type}_{companion_id}"
    quest_obj = {
        "id": q_id,
        "title": params["title"],
        "flavor_text": params["flavor_text"],
        "objectives": objectives_list,
        "raw_objectives": target_task["objectives"],
        "completion_text": f"Mission accomplished. {params['title']} successful.",
        "reward": {"type": params["reward_type"], "target": companion_id},
        "difficulty": difficulty_override
    }
    
    if "generated_side_quests" not in save_data: save_data["generated_side_quests"] = []
    save_data["generated_side_quests"] = [q for q in save_data["generated_side_quests"] if q["id"] != q_id]
    save_data["generated_side_quests"].append(quest_obj)
    
    if "active_side_quests" not in save_data: save_data["active_side_quests"] = []
    if q_id not in save_data["active_side_quests"]: save_data["active_side_quests"].append(q_id)
    
    if "quest_progress" not in save_data: save_data["quest_progress"] = {}
    save_data["quest_progress"][q_id] = [False] * len(objectives_list)
    
    io.save_json(config.PATHS["save_data"], save_data)
    return quest_obj

# ----------------------------------------------------------------------
# REWARD PROCESSING
# ----------------------------------------------------------------------

def grant_task_reward(difficulty, save_data, is_emergency=False, bonus_mult=1.0, task_tags=None, raid_tags=None):
    """
    Calculates and delivers rewards for a completed task.
    UPDATED: Now returns the reward package instead of sending commands directly.
    """
    # 1. Base Package
    pkg = loot.calculate_reward_package("task", difficulty, save_data)
    
    # 2. Companion Multipliers
    import etw_buffs 
    comp_bonuses = etw_buffs.calculate_companion_bonuses(save_data, task_tags, raid_tags)
    
    pkg["xp"] = int(pkg["xp"] * comp_bonuses["xp"])
    pkg["caps"] = int(pkg["caps"] * comp_bonuses["caps"])
    pkg["scrip"] = int(pkg["scrip"] * comp_bonuses["scrip"])
    
    # 3. Emergency / Bonus Objective Multipliers
    if is_emergency or bonus_mult > 1.0:
        base_boost = 1.25 if is_emergency else 1.0
        total_mult = base_boost * bonus_mult
        pkg["xp"] = int(pkg["xp"] * total_mult)
        pkg["caps"] = int(pkg["caps"] * total_mult)
        pkg["scrip"] = int(pkg["scrip"] * total_mult)
        
    # 4. Apply to State
    save_data["scrip"] += pkg["scrip"]
    save_data["current_xp"] = save_data.get("current_xp", 0) + pkg["xp"]
    
    companions.add_companion_xp(save_data, pkg["xp"])
    
    ms_context = {"event": "task_complete", "difficulty": difficulty}
    companions.check_milestones(save_data, ms_context)
    
    # 5. [REMOVED] Deliver via Console (Direct Bridge Call)
    # The bridge call here caused race conditions. 
    # The package is now returned to the raid manager for aggregation.
    # cmds = []
    # if pkg["caps"] > 0: cmds.append(f"player.additem 0000000F {pkg['caps']}")
    # if pkg["xp"] > 0: cmds.append(f"player.rewardxp {pkg['xp']}")
    # for it in pkg["items"]: cmds.append(f"player.additem {it['code']} {it['qty']}")
    # game_path = save_data.get("game_install_path", "")
    # if game_path:
    #     bridge.process_game_commands(game_path, cmds)
    
    # 6. Finalize
    save_data["reputation"] = stats.compute_reputation(save_data)
    loot.log_reward_history(save_data, f"Task ({difficulty.capitalize()})", pkg)
    io.save_json(config.PATHS["save_data"], save_data)
    
    return pkg

def process_raid_task_completion(save_data):
    """
    Called at the end of a raid. Checks active tasks for completion.
    Returns metrics AND accumulated rewards for the master batch.
    """
    tasks_list = save_data.get("tasks", [])
    surviving_tasks = []
    
    tasks_completed = 0
    diffs = set()
    emergency_count = 0
    bonus_count = 0
    
    accumulated_rewards = [] # New aggregator
    
    for t in tasks_list:
        if t.get("ready_to_complete"):
            diff = t.get("difficulty", "easy")
            is_em = t.get("is_emergency", False)
            mult = t.get("reward_mult", 1.0)
            tags = t.get("tags", [])
            
            # Capture the returned package
            pkg = grant_task_reward(diff, save_data, is_emergency=is_em, bonus_mult=mult, task_tags=tags)
            accumulated_rewards.append(pkg)
            
            save_data["total_completed_tasks"] += 1
            if diff == "easy": save_data["easy_completed"] += 1
            elif diff == "medium": save_data["medium_completed"] += 1
            elif diff == "hard": save_data["hard_completed"] += 1
            
            tasks_completed += 1
            diffs.add(diff)
            if is_em: 
                save_data["emergency_completed"] += 1
                emergency_count += 1
            if "bonus_objective" in tags: 
                bonus_count += 1
        else:
            if "original_objectives" in t:
                 t["objectives"] = copy.deepcopy(t["original_objectives"])
                 t["ready_to_complete"] = False
            surviving_tasks.append(t)
            
    save_data["tasks"] = surviving_tasks
    
    return {
        "tasks_completed": tasks_completed,
        "completed_difficulties": diffs,
        "emergency_count": emergency_count,
        "bonus_count": bonus_count,
        "accumulated_rewards": accumulated_rewards # Added to return
    }