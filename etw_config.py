import os

# ----------------------------------------------------------------------
# GLOBAL CONSTANTS & CONFIGURATION
# ----------------------------------------------------------------------
# This module must REMAIN dependency-free to prevent circular imports.
# It serves as the static backbone for the application.

# --------------------------
# 1. File Paths
# --------------------------
PATHS = {
    # System
    "save_data": "save_data.json",
    "ahk_script": "run_bat.ahk",
    "config_tuning": "config_tuning.json",
    "version_log": "version_log.txt",
    
    # Content - Core
    "content_raids": "content_raids.json",
    "content_tasks": "content_tasks.json",
    "content_hideout": "content_hideout.json",
    "content_departures": "content_departures.json",
    
    # Content - Loot DB
    "world_pool": "world_pool.json",
    "weapons": "loot_weapons.json",
    "armor": "loot_armor.json",
    "consumables": "loot_consumables.json",
    "ammo": "loot_ammo.json",
    "misc": "loot_misc.json",
    "blueprints": "loot_blueprints.json", # NEW: Workbench Database
    
    # Content - Economy & Quests
    "shop_items": "shop_items.json",
    "side_quests": "side_quests.json",
    "main_quests": "main_quests.json",
    "character_themes": "character_themes.json",
    "starter_loadouts": "starter_loadouts.json",
    "ambushes": "ambushes.json", 
    "content_bar": "content_bar.json",
    "content_intel": "content_intel.json",
    "content_companions": "content_companions.json", 
    "content_random_npcs": "content_random_npcs.json",
    
    "content_npcs": "content_npcs.json" 
}

# --------------------------
# 2. Bridge Constants
# --------------------------
# Redefined here to avoid importing etw_bridge directly in config consumers
BATCH_FILENAME = "mng.txt"

# UNIFIED BASELINE FILE (No Extension)
# Both stats and inventory will be dumped here.
# Removed .txt because Creation Engine 'scof' creates extensionless files.
SCAN_LOG_FILENAME = "etw_baseline"
INVENTORY_LOG_FILENAME = "etw_baseline"

# --------------------------
# 3. Game Coordinates
# --------------------------
# Teleport coordinates for Returning to Town
# UPDATED: Switched to Exterior/Landing cells for stability.
HOMEPOINTS = {
    "Megaton": "coc MegatonTown", 
    "Tenpenny Tower": "coc TenpennyTowerExterior",
    "Rivet City": "coc RivetCityLanding"
}