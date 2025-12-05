import random
import time
import copy

# Foundation
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_bridge as bridge
import etw_loot as loot
import etw_tasks as tasks
import etw_task_generator as task_gen
import etw_companions as companions
import etw_hideout as hideout
import etw_buff_manager as buff_manager
import etw_raid_cleanup as raid_cleanup
import etw_stats as stats 

# ----------------------------------------------------------------------
# SHARED HELPERS
# ----------------------------------------------------------------------

def _get_homepoint_cmd(save_data):
    hp = save_data.get("homepoint", "Megaton")
    return config.HOMEPOINTS.get(hp, config.HOMEPOINTS["Megaton"])

def _process_raid_return_shared(save_data, duration):
    """
    Common logic run after both Death and Extraction.
    """
    elapsed_minutes = duration / 60.0
    
    # 1. Update Hideout Production
    if elapsed_minutes > 0:
        hideout.update_hideout_timers(save_data, elapsed_minutes)
    
    # 2. Age Tasks
    tasks._age_tasks(save_data)
    
    # 3. Restore Threat Level if forced
    if save_data.get("original_threat_level"):
        save_data["threat_level"] = save_data.get("original_threat_level")
        save_data["original_threat_level"] = None
        
    # 4. Advance Cycle (Inline Logic to avoid engine import)
    cycle = save_data.get("day_cycle", 0) + 1
    save_data["day_cycle"] = cycle
    
    # Load modifier config fresh to avoid state stale issues
    conf = io.load_json(config.PATHS["content_raids"])
    mods = list(conf.get("raid_modifiers", {}).keys())
    if mods:
        new_mod = random.choice(mods)
        save_data["current_raid_modifier"] = new_mod
    
    # 5. Refresh Board
    tasks.refresh_taskboard(save_data) 
    
    io.save_json(config.PATHS["save_data"], save_data)

def _get_companion_context(save_data):
    """
    Helper to extract companion display data for transition screens.
    """
    c_id, c_data = companions.get_active_companion(save_data)
    if not c_id: return None
    
    roster = companions.load_companion_roster()
    c_def = roster.get(c_id, {})
    
    lvl = c_data.get("level", 1)
    xp = c_data.get("xp", 0)
    
    curr_base = companions.LEVEL_XP_THRESHOLDS.get(lvl, 0)
    next_xp = companions.LEVEL_XP_THRESHOLDS.get(lvl + 1, 99999)
    
    if lvl >= 5:
        pct = 1.0
        txt = "MAX"
    else:
        req = next_xp - curr_base
        progress = xp - curr_base
        pct = min(1.0, progress / req) if req > 0 else 0
        txt = f"{int(pct * 100)}%"

    return {
        "name": c_def.get("name", "Companion"),
        "level": lvl,
        "xp_pct": pct,
        "xp_text": txt
    }

# ----------------------------------------------------------------------
# RAID START
# ----------------------------------------------------------------------

def process_raid_start(save_data):
    """
    Sets up the raid state and prepares commands. 
    UPDATED: Uses coc <CellID> based on difficulty selection.
    """
    # 1. Update State
    save_data["raid_active"] = True
    save_data["last_raid_start_timestamp"] = time.time()
    save_data["raid_paused"] = False
    save_data["raid_paused_elapsed"] = 0.0
    save_data["raids_started"] = save_data.get("raids_started", 0) + 1
    
    save_data["ambush_state"] = {
        "last_check_time": time.time(), 
        "cooldown_until": 0.0, 
        "ambushes_triggered": 0
    }
    
    # 2. Setup Extractions
    pool_data = io.load_json(config.PATHS["world_pool"], {})
    extractions_pool = pool_data.get("extractions", [])
    
    mod_id = save_data.get("current_raid_modifier")
    raids_content = io.load_json(config.PATHS["content_raids"])
    mod = raids_content.get("raid_modifiers", {}).get(mod_id, {})
    
    # Modifier: Extraction Count
    ext_effect = mod.get("effects", {}).get("extraction")
    num_extracts = 4
    if ext_effect:
        if ext_effect.get("type") == "fixed": 
            num_extracts = ext_effect.get("count", 2)
        elif ext_effect.get("type") == "range": 
            num_extracts = random.randint(ext_effect.get("min", 6), ext_effect.get("max", 8))
            
    if extractions_pool: 
        save_data["current_extractions"] = random.sample(
            extractions_pool, 
            min(len(extractions_pool), num_extracts)
        )
    
    # Modifier: Wasteland in Need
    if mod_id == "wasteland_in_need":
        threat = save_data.get("threat_level", 1)
        count = 1 if threat < 3 else (2 if threat < 6 else 3)
        
        all_ids = [t.get("task_number", 0) for t in save_data.get("tasks", [])] + \
                  [t.get("task_number", 0) for t in save_data.get("taskboard_pool", [])]
        next_id = (max(all_ids) + 1) if all_ids else 1
        
        for _ in range(count):
            new_task = task_gen.generate_task(save_data, next_id, force_emergency=True)
            save_data["tasks"].append(new_task)
            next_id += 1

    # Modifier: Force Threat
    threat_effect = mod.get("effects", {}).get("threat")
    if threat_effect and threat_effect.get("type") == "force_max":
        save_data["original_threat_level"] = save_data.get("threat_level", 1)
        save_data["threat_level"] = 5
    
    io.save_json(config.PATHS["save_data"], save_data)
    
    # 3. Logic for Departure (UPDATED)
    # Load Departures Config
    departures_map = io.load_json(config.PATHS["content_departures"], {})
    
    # Determine Difficulty Tier
    selected_diff = save_data.get("raid_difficulty_selection", "Easy")
    
    # Fallback if key missing (shouldn't happen with UI limits)
    if selected_diff not in departures_map:
        selected_diff = "Easy"
        
    tier_locations = departures_map.get(selected_diff, [])
    
    # Fallback to defaults if JSON empty
    if not tier_locations:
        tier_locations = [{"name": "Megaton", "cell": "MegatonTown"}]
        
    start_point = random.choice(tier_locations)
    
    # Store Location info for UI Transition Screen
    save_data["current_raid_location_name"] = start_point["name"]
    save_data["current_raid_difficulty"] = selected_diff
    io.save_json(config.PATHS["save_data"], save_data) # Resave for UI access
    
    game_path = save_data.get("game_install_path", "")
    
    if game_path and start_point.get("cell"):
        # COMMAND SWITCH: Use coc instead of moveto or setpos
        cmds = [f"coc {start_point['cell']}"]
        
        # UPDATED: Use fast execution (verify=False) to avoid handshake delay on teleport
        bridge.process_game_commands(game_path, cmds, verify=False)
    
    return {"destination": start_point["name"] if start_point else "Wasteland"}

# ----------------------------------------------------------------------
# RAID ACTIONS (SOS FLARE)
# ----------------------------------------------------------------------

def use_sos_flare(save_data):
    """
    Attempts to trigger an emergency extraction using a consumable flare.
    """
    if not save_data.get("raid_active"):
        return {"success": False, "message": "No active raid."}
        
    inv = save_data.get("inventory", {})
    if inv.get("sos_flare", 0) <= 0:
        return {"success": False, "message": "No SOS Flares in inventory."}
        
    start_t = save_data.get("last_raid_start_timestamp", 0)
    paused_t = save_data.get("raid_paused_elapsed", 0.0)
    elapsed = time.time() - start_t - paused_t
    
    UNLOCK_TIME = 1500 # 25 Minutes
    
    if elapsed < UNLOCK_TIME:
        rem_min = int((UNLOCK_TIME - elapsed) // 60)
        return {"success": False, "message": f"Signal blocked! Available in {rem_min} mins."}
        
    mod_id = save_data.get("current_raid_modifier")
    if mod_id == "watching_eyes" or mod_id == "spicy_sieverts":
        return {"success": False, "message": "Flare jammed by atmospheric interference!"}

    inv["sos_flare"] -= 1
    # NOTE: The actual transition call is handled by the UI calling prepare_extraction(is_sos=True)
    # This function validates logic and consumes item.
    
    return {"success": True, "message": "Flare deployed! Vertibird inbound..."}

# ----------------------------------------------------------------------
# RAID DEATH
# ----------------------------------------------------------------------

def prepare_death(save_data):
    """
    Step 1 of Death: Updates stats, fails tasks, saves state.
    """
    save_data["raid_active"] = False
    save_data["raids_died"] += 1
    duration = time.time() - save_data.get("last_raid_start_timestamp", time.time())
    
    for t in save_data.get("tasks", []):
        if "original_objectives" in t:
            t["objectives"] = copy.deepcopy(t["original_objectives"])
            t["ready_to_complete"] = False
            
    stats.adjust_threat_on_failure(save_data)
    _process_raid_return_shared(save_data, duration)
    
    ms_context = {
        "event": "raid_end", "success": False, "death_occurred": True, "duration": duration
    }
    companions.check_milestones(save_data, ms_context)
    io.save_json(config.PATHS["save_data"], save_data)
    
    mins = int(duration // 60)
    secs = int(duration % 60)
    
    comp_context = _get_companion_context(save_data)

    return {
        "outcome": "KIA",
        "duration_str": f"{mins:02}:{secs:02}",
        "tasks_str": "0",
        "xp": 0, "caps": 0, "scrip": 0, "loot_count": 0,
        "companion": comp_context
    }

def execute_death_sequence(save_data):
    """
    Step 2 of Death: The 'Grim Reaper' Sequence.
    """
    raid_cleanup.execute_death_step_1_scan(save_data)
    raid_cleanup.execute_death_step_2_losses(save_data)
    raid_cleanup.execute_death_step_3_debuff(save_data)

# ----------------------------------------------------------------------
# RAID EXTRACTION (REFACTORED: ECHO PROTOCOL + DIFFICULTY SCALING)
# ----------------------------------------------------------------------

def _aggregate_extraction_rewards(raid_rewards, accumulated_rewards):
    """
    Combines the Time-Based reward with all Task-Based rewards into one Master Bundle.
    """
    master = {
        "xp": raid_rewards.get("xp", 0),
        "caps": raid_rewards.get("caps", 0),
        "scrip": raid_rewards.get("scrip", 0),
        "items": list(raid_rewards.get("items", []))
    }
    
    for pkg in accumulated_rewards:
        master["xp"] += pkg.get("xp", 0)
        master["caps"] += pkg.get("caps", 0)
        master["scrip"] += pkg.get("scrip", 0)
        master["items"].extend(pkg.get("items", []))
        
    return master

def prepare_extraction(save_data, is_sos=False):
    """
    Step 1 of Extract: Aggregates Rewards, Sends BIG BATCH, Waits for Echo.
    If Echo is confirmed -> Commits to Save Data.
    UPDATED: Handles Difficulty Scaling Multipliers.
    """
    # 1. Apply Difficulty Bonuses (Inject Fortune BEFORE calculation if VeryHard)
    difficulty = save_data.get("raid_difficulty_selection", "Easy")
    temp_fortune_buff = None
    
    if difficulty == "VeryHard":
        # Inject temporary buff for calculation logic
        temp_fortune_buff = {"id": "temp_vh_fortune", "name": "High Stakes (+1 Fortune)"}
        save_data["active_buffs"].append(temp_fortune_buff)
        # Note: We do NOT save_json here, this is ephemeral for math logic
        
    # 2. Calculate Metrics (Read-Only Logic)
    duration = time.time() - save_data.get("last_raid_start_timestamp", time.time())
    
    # process_raid_task_completion returns the list of reward packages but does NOT send commands
    # This will now use the injected Fortune buff for better loot rolls
    completion_metrics = tasks.process_raid_task_completion(save_data)
    
    # Calculate Raid Time Bonus
    time_rewards = loot.calculate_extraction_reward(duration, save_data)
    
    # 3. Clean up Temporary Buff
    if temp_fortune_buff:
        save_data["active_buffs"].remove(temp_fortune_buff)
        # Still do not save yet
    
    # 4. Apply Modifier Bonuses
    raids_content = io.load_json(config.PATHS["content_raids"])
    mod_id = save_data.get("current_raid_modifier")
    mod = raids_content.get("raid_modifiers", {}).get(mod_id, {})
    reward_effect = mod.get("effects", {}).get("reward")
    
    if reward_effect:
        cond = reward_effect.get("condition", {})
        apply_bonus = False
        duration_min = duration / 60.0
        
        if cond.get("type") == "raid_time_greater_than":
            if duration_min > cond.get("minutes", 0): apply_bonus = True
        elif cond.get("type") == "raid_time_less_than":
            if duration_min < cond.get("minutes", 999): apply_bonus = True
            
        if apply_bonus:
            mult = reward_effect.get("multiplier", 1.0)
            time_rewards["xp"] = int(time_rewards["xp"] * mult)
            time_rewards["caps"] = int(time_rewards["caps"] * mult)
            time_rewards["scrip"] = int(time_rewards["scrip"] * mult)

    # 5. AGGREGATE EVERYTHING
    master_pkg = _aggregate_extraction_rewards(time_rewards, completion_metrics.get("accumulated_rewards", []))
    
    # 6. Apply Global Difficulty Multiplier to the MASTER BATCH
    diff_mult = 1.0
    if difficulty == "Medium": diff_mult = 1.5
    elif difficulty == "Hard": diff_mult = 2.0
    elif difficulty == "VeryHard": diff_mult = 3.0
    
    if diff_mult > 1.0:
        master_pkg["xp"] = int(master_pkg["xp"] * diff_mult)
        master_pkg["caps"] = int(master_pkg["caps"] * diff_mult)
        master_pkg["scrip"] = int(master_pkg["scrip"] * diff_mult)
    
    # 7. Construct the BIG BATCH
    big_batch_cmds = []
    
    if master_pkg["caps"] > 0: 
        big_batch_cmds.append(f"player.additem 0000000F {master_pkg['caps']}")
        
    if master_pkg["xp"] > 0: 
        big_batch_cmds.append(f"player.rewardxp {master_pkg['xp']}")
        
    for it in master_pkg["items"]: 
        big_batch_cmds.append(f"player.additem {it['code']} {it['qty']}")
        
    # 8. EXECUTE WITH VERIFICATION (The Echo)
    game_path = save_data.get("game_install_path", "")
    verification_success = False
    
    if game_path:
        # This call BLOCKS until confirmed or timeout
        verification_success = bridge.execute_batch_with_verification(game_path, big_batch_cmds)
    else:
        # Debug mode fallback
        verification_success = True 

    # 9. DECISION POINT
    if not verification_success:
        print("[Raid] EXTRACTION FAILED: Game did not echo.")
        # Return a Failure Context so UI can handle it (e.g. "Retry Extraction")
        return {
            "outcome": "ERROR",
            "message": "Game connection failed. Rewards not applied.",
            "retry_available": True
        }

    # 10. COMMIT (Only if Verified)
    # Now it is safe to update the "Bank Account" (Save Data)
    save_data["raid_active"] = False
    save_data["raids_extracted"] = save_data.get("raids_extracted", 0) + 1
    if is_sos: 
        save_data["sos_extracts"] = save_data.get("sos_extracts", 0) + 1
        
    save_data["scrip"] += master_pkg["scrip"]
    save_data["current_xp"] = save_data.get("current_xp", 0) + master_pkg["xp"]
    
    companions.update_ultimate_progress(save_data, duration / 60.0)
    _process_raid_return_shared(save_data, duration)
    
    stats.adjust_threat_on_extraction(
        save_data, 
        completion_metrics["tasks_completed"], 
        completion_metrics["completed_difficulties"]
    )
    
    ms_context = {
        "event": "raid_end", 
        "success": True, 
        "death_occurred": False, 
        "duration": duration, 
        "emergency_count": completion_metrics["emergency_count"], 
        "bonus_count": completion_metrics["bonus_count"], 
        "sos_used": is_sos
    }
    companions.check_milestones(save_data, ms_context)
    loot.log_reward_history(save_data, "Raid Extraction", master_pkg)
    
    io.save_json(config.PATHS["save_data"], save_data)
    
    # 11. Return Success Context
    mins = int(duration // 60)
    secs = int(duration % 60)
    comp_context = _get_companion_context(save_data)
    
    return {
        "outcome": "EXTRACTED",
        "duration_str": f"{mins:02}:{secs:02}",
        "tasks_str": str(completion_metrics["tasks_completed"]),
        "xp": master_pkg["xp"],
        "caps": master_pkg["caps"],
        "scrip": master_pkg["scrip"],
        "loot_count": len(master_pkg["items"]),
        "rewards_package": master_pkg, # The UI now sees the FULL aggregated list
        "companion": comp_context
    }

def execute_extraction_sequence(save_data, context):
    """
    Step 2 of Extract: Debuff & Cleanup (Rewards already sent in Step 1).
    """
    # NOTE: Rewards are now handled inside prepare_extraction via Big Batch.
    # We only need to do cleanup here.
    raid_cleanup.execute_extraction_step_2_debuff(save_data)

# ----------------------------------------------------------------------
# FINALIZATION
# ----------------------------------------------------------------------

def finalize_raid_teleport(save_data):
    """
    Step 3 (Final): Teleport.
    """
    raid_cleanup.perform_teleport_home(save_data)

# ----------------------------------------------------------------------
# BUFF MANAGEMENT
# ----------------------------------------------------------------------

def process_raid_extraction(save_data, is_sos=False):
    return prepare_extraction(save_data, is_sos)