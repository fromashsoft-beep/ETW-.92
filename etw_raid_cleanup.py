import os
import time

# Foundation
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_bridge as bridge
import etw_inventory as inventory
import etw_buff_manager as buff_manager

# ----------------------------------------------------------------------
# HELPER: TELEPORT
# ----------------------------------------------------------------------

def perform_teleport_home(save_data):
    """
    Sends the teleport command as a strictly isolated batch.
    This is the FINAL step.
    """
    game_path = save_data.get("game_install_path", "")
    if not game_path: return

    hp = save_data.get("homepoint", "Megaton")
    # FIX: Access HOMEPOINTS from config, not engine
    cmd = config.HOMEPOINTS.get(hp, config.HOMEPOINTS["Megaton"])
    
    # Critical: Teleport must be the ONLY command in its batch
    # This now uses the global verification bridge, which is fine for teleport too
    bridge.process_game_commands(game_path, [cmd])
    
    # Wait for AHK execution
    bridge.wait_for_ahk()

# ----------------------------------------------------------------------
# DEATH SEQUENCE (GRANULAR STEPS)
# ----------------------------------------------------------------------

def execute_death_step_1_scan(save_data):
    """
    Step 1: Trigger Scan & Sync Source of Truth.
    """
    game_path = save_data.get("game_install_path", "")
    if not game_path: return

    # Trigger the dump
    bridge.trigger_inventory_scan(game_path)
    
    # TIMING FIX: Smart Poll
    log_path = os.path.join(game_path, config.INVENTORY_LOG_FILENAME)
    bridge.await_file_creation(log_path, timeout=5.0)
    
    # Now safe to parse
    inventory.perform_full_inventory_sync(save_data)

def execute_death_step_2_losses(save_data):
    """
    Step 2: Calculate & Remove Losses.
    UPDATED: Now clears insurance list after processing.
    """
    game_path = save_data.get("game_install_path", "")
    if not game_path: return

    removal_cmds, removed_items_data = inventory.calculate_death_losses(save_data)
    
    # Clear Insurance (Consumed on death to save items)
    save_data["insured_items"] = []
    io.save_json(config.PATHS["save_data"], save_data)
    
    if removed_items_data:
        inventory.update_local_inventory(save_data, removed_items=removed_items_data)

    if removal_cmds:
        bridge.process_game_commands(game_path, removal_cmds)
        bridge.wait_for_ahk()

def execute_death_step_3_debuff(save_data):
    """
    Step 3: Remove Companion Buffs.
    """
    game_path = save_data.get("game_install_path", "")
    if not game_path: return

    buff_manager.remove_companion_buffs(save_data)
    bridge.wait_for_ahk()

def execute_death_step_4_teleport(save_data):
    """
    Step 4: Teleport Home (Final).
    """
    perform_teleport_home(save_data)

# ----------------------------------------------------------------------
# EXTRACTION SEQUENCE (GRANULAR STEPS)
# ----------------------------------------------------------------------

def execute_extraction_step_1_rewards(save_data, context):
    """
    Step 1: Grant Rewards.
    UPDATE: This logic is now handled via the 'Big Batch' in etw_raid.prepare_extraction.
    We retain this function as a stub for local JSON updates if needed.
    """
    rewards = context.get("rewards_package", {})
    items_to_add = rewards.get("items", [])
    caps_to_add = rewards.get("caps", 0)
    
    # Update local Source of Truth (JSON) only. NO BRIDGE COMMANDS.
    if items_to_add or caps_to_add > 0:
        inventory.update_local_inventory(save_data, added_items=items_to_add, caps_change=caps_to_add)

def execute_extraction_step_2_debuff(save_data):
    """
    Step 2: Remove Companion Buffs AND Clear Insurance.
    """
    # UPDATED: Clear Insurance (Consumed on extraction too, per "1 raid" rule)
    save_data["insured_items"] = []
    io.save_json(config.PATHS["save_data"], save_data)

    game_path = save_data.get("game_install_path", "")
    if not game_path: return

    buff_manager.remove_companion_buffs(save_data)
    bridge.wait_for_ahk()

def execute_extraction_step_3_teleport(save_data):
    """
    Step 3: Teleport Home (Final).
    """
    perform_teleport_home(save_data)

# ----------------------------------------------------------------------
# LEGACY WRAPPERS
# ----------------------------------------------------------------------

def execute_death_sequence(save_data):
    execute_death_step_1_scan(save_data)
    execute_death_step_2_losses(save_data)
    execute_death_step_3_debuff(save_data)
    execute_death_step_4_teleport(save_data)

def finalize_extraction(save_data, context):
    # execute_extraction_step_1_rewards(save_data, context) # Handled by Big Batch + Sync Stub
    execute_extraction_step_2_debuff(save_data)
    execute_extraction_step_3_teleport(save_data)