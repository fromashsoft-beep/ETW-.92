import tkinter as tk
from tkinter import filedialog, messagebox
import time
import etw_engine as engine
import etw_bridge as bridge
import etw_raid as raid
import etw_inventory as inventory # Added

# ----------------------------------------------------------------------
# BUILDERS
# ----------------------------------------------------------------------

def build_settings_screen(app, frame):
    """
    Constructs the Settings UI.
    """
    # 1. Header
    tk.Label(frame, text="Settings", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=20)
    
    # 2. Input Settings (F5 Toggle)
    keys_frame = tk.Frame(frame, bg="#222222", bd=2, relief="ridge")
    keys_frame.pack(fill="x", padx=50, pady=10)
    
    tk.Label(keys_frame, text="Input Configuration", fg="#FFAA00", bg="#222222", font=("Courier", 12, "bold")).pack(pady=5)
    
    # Checkbox logic
    current_setting = app.save_data.get("user_settings", {}).get("enable_f5_hotkey", True)
    app.f5_var = tk.BooleanVar(value=current_setting)
    
    cb = tk.Checkbutton(
        keys_frame, 
        text="Enable F5 Quick Scan (Global Hotkey)", 
        variable=app.f5_var, 
        command=lambda: _toggle_f5(app),
        bg="#222222", fg="#FFFFFF", selectcolor="#333333", activebackground="#222222", activeforeground="#FFFFFF",
        font=("Courier", 10)
    )
    cb.pack(pady=10)
    
    tk.Label(keys_frame, text="Press F5 in-game to update stats/inventory instantly.", fg="#AAAAAA", bg="#222222", font=("Courier", 9, "italic")).pack(pady=(0, 10))

    # 3. Path Selection
    path_frame = tk.Frame(frame, bg="#111111")
    path_frame.pack(fill="x", padx=50, pady=10)
    
    tk.Label(path_frame, text="Fallout 3 Directory:", fg="#00FFFF", bg="#111111", font=("Courier", 10, "bold")).pack(anchor="w")
    
    current_path = app.save_data.get("game_install_path", "Not Set")
    app.path_display_label = tk.Label(path_frame, text=current_path, fg="#555555", bg="#222222", relief="sunken", font=("Courier", 9))
    app.path_display_label.pack(fill="x", pady=5)
    
    tk.Button(path_frame, text="Browse...", command=lambda: _browse_game_path(app), bg="#333333", fg="#FFFFFF", font=("Courier", 9)).pack(anchor="e")
    
    # 4. Gameplay Settings (Companion Buffs & Ambush)
    comp_frame = tk.Frame(frame, bg="#111111", bd=2, relief="groove")
    comp_frame.pack(fill="x", padx=50, pady=10)
    
    tk.Label(comp_frame, text="Gameplay Systems", fg="#FFAA00", bg="#111111", font=("Courier", 12, "bold")).pack(pady=5)
    
    # Companion Buffs Checkbox
    app.companion_buffs_var = tk.BooleanVar(value=app.save_data.get("companion_buffs", False))
    
    tk.Checkbutton(
        comp_frame, 
        text="Enable Companion Buffs (Modifies Stats)", 
        variable=app.companion_buffs_var, 
        command=lambda: _toggle_companion_buffs(app),
        bg="#111111", fg="#FFFFFF", selectcolor="#222222", activebackground="#111111", activeforeground="#FFFFFF",
        font=("Courier", 10)
    ).pack(pady=5)

    # Ambush Mechanic Checkbox (NEW)
    ambush_setting = app.save_data.get("user_settings", {}).get("enable_ambush_mechanic", True)
    app.ambush_var = tk.BooleanVar(value=ambush_setting)

    tk.Checkbutton(
        comp_frame,
        text="Enable Ambush Mechanic",
        variable=app.ambush_var,
        command=lambda: _toggle_ambush_mechanic(app),
        bg="#111111", fg="#FFFFFF", selectcolor="#222222", activebackground="#111111", activeforeground="#FFFFFF",
        font=("Courier", 10)
    ).pack(pady=5)
    
    # 5. Maintenance / Debug
    btn_row = tk.Frame(comp_frame, bg="#111111")
    btn_row.pack(pady=10)
    
    app.settings_feedback_lbl = tk.Label(comp_frame, text="", fg="#00FF00", bg="#111111", font=("Courier", 9))
    app.settings_feedback_lbl.pack(pady=2)
    
    tk.Button(btn_row, text="Manual Scan (Baseline)", command=lambda: _manual_scan(app), bg="#003300", fg="#00FF00", font=("Courier", 9)).pack(side="left", padx=10)
    tk.Button(btn_row, text="RESET STATS TO BASELINE", command=lambda: _manual_hard_reset(app), bg="#550000", fg="#FFFFFF", font=("Courier", 9, "bold")).pack(side="left", padx=10)
    
    # 6. Save/Exit
    # Renamed from "Save & Return to Town" -> "Save & Return"
    tk.Button(frame, text="Save & Return", command=lambda: _save_and_exit(app), bg="#003300", fg="#00FF00", font=("Courier", 14, "bold"), width=25).pack(pady=20)

# ----------------------------------------------------------------------
# ACTIONS
# ----------------------------------------------------------------------

def _toggle_f5(app):
    """
    Immediate toggle of the hotkey listener.
    """
    enabled = app.f5_var.get()
    if hasattr(app, 'hotkey_manager'):
        app.hotkey_manager.set_enabled(enabled)
    
    # Also save to config immediately
    if "user_settings" not in app.save_data:
        app.save_data["user_settings"] = {}
    app.save_data["user_settings"]["enable_f5_hotkey"] = enabled
    engine.save_save_data(app.save_data)

def _browse_game_path(app):
    path = filedialog.askdirectory()
    if path:
        app.save_data["game_install_path"] = path
        app.path_display_label.config(text=path)
        engine.save_save_data(app.save_data)

def _toggle_companion_buffs(app):
    app.save_data["companion_buffs"] = app.companion_buffs_var.get()
    engine.save_save_data(app.save_data)

def _toggle_ambush_mechanic(app):
    """
    Toggles the Ambush Mechanic setting.
    """
    enabled = app.ambush_var.get()
    if "user_settings" not in app.save_data:
        app.save_data["user_settings"] = {}
    app.save_data["user_settings"]["enable_ambush_mechanic"] = enabled
    engine.save_save_data(app.save_data)

def _manual_scan(app):
    game_path = app.save_data.get("game_install_path", "")
    if not game_path:
        app.show_temporary_text(app.settings_feedback_lbl, "Game Path Not Set!", "#FF0000")
        return

    bridge.trigger_baseline_scan(game_path)
    app.settings_feedback_lbl.config(text="Scanning... Please Wait...")
    
    # Start Non-Blocking Polling Loop
    # We pass the start time to handle timeouts
    app.after(100, lambda: _poll_manual_scan_result(app, time.time()))

def _poll_manual_scan_result(app, start_time):
    game_path = app.save_data.get("game_install_path", "")
    
    # NON-BLOCKING READ
    result = bridge.read_baseline_scan(game_path, blocking=False)
    
    if result:
        # SUCCESS
        if "baseline" not in app.save_data: app.save_data["baseline"] = {}
        app.save_data["baseline"]["level"] = result["level"]
        app.save_data["baseline"].update(result["stats"])
        
        # Sync to JSON source of truth immediately after manual scan
        inventory.perform_full_inventory_sync(app.save_data)
        
        engine.save_save_data(app.save_data)
        app.show_temporary_text(app.settings_feedback_lbl, "Baseline Updated!", "#00FF00")
        
    else:
        # CHECK TIMEOUT
        elapsed = time.time() - start_time
        if elapsed > 15.0:
            app.show_temporary_text(app.settings_feedback_lbl, "Scan Failed (Timeout)", "#FF0000")
        else:
            # RETRY IN 100ms
            app.after(100, lambda: _poll_manual_scan_result(app, start_time))

def _manual_hard_reset(app):
    """
    Removes companion buffs and forces all baseline stats (SPECIAL/Skills) 
    back to the last scanned values via console commands.
    """
    game_path = app.save_data.get("game_install_path", "")
    if not game_path:
        app.show_temporary_text(app.settings_feedback_lbl, "Game Path Not Set!", "#FF0000"); return
        
    if not messagebox.askyesno("Hard Reset", "This will FORCE your in-game stats to match the last scanned baseline.\nOnly use this if stats are bugged.\n\nContinue?"): 
        return
    
    baseline = app.save_data.get("baseline", {})
    if not baseline:
        app.show_temporary_text(app.settings_feedback_lbl, "No baseline data found. Perform manual scan first!", "#FF0000"); return
    
    # 1. Remove currently active companion buffs (if any)
    raid.remove_companion_buffs(app.save_data)
    
    # 2. Compile commands to reset all known stats to baseline value
    reset_cmds = []
    
    # Use STATS_COVERED list from etw_bridge to ensure coverage
    import etw_bridge as bridge_alias
    
    # Iterate over all possible stat keys to ensure a complete reset
    for stat in bridge_alias.STATS_COVERED:
        # We use 'setav' for a hard reset to the base value
        base_val = int(baseline.get(stat, 0))
        if base_val > 0:
            reset_cmds.append(f"player.setav {stat} {base_val}")
    
    # 3. Execute commands
    if reset_cmds:
        # Execute the full reset batch
        bridge.process_game_commands(game_path, reset_cmds)
        app.show_temporary_text(app.settings_feedback_lbl, "STAT RESET COMMANDS SENT. Wait for game processing.", "#FFFF00", duration=3000)
    else:
        app.show_temporary_text(app.settings_feedback_lbl, "Baseline empty or missing stats. Reset cancelled.", "#FF0000")

def _save_and_exit(app):
    # Ensure all vars are synced
    _toggle_f5(app) 
    _toggle_companion_buffs(app)
    _toggle_ambush_mechanic(app)
    
    # Navigation logic
    if hasattr(app, 'settings_next_screen') and app.settings_next_screen == "character_gen":
        app.start_character_gen()
        app.settings_next_screen = None
    else:
        app.show_town_screen()