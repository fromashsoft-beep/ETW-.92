import tkinter as tk
import time
import etw_engine as engine
import etw_raid as raid 
import etw_companions as companions # Needs to be available for helper
import etw_inventory as inventory # For accessing Source of Truth data

# ----------------------------------------------------------------------
# HELPER: Companion XP Drawing
# ----------------------------------------------------------------------
def _draw_companion_xp_status(app):
    """
    Calculates and draws the XP bar and companion status labels on the departing screen.
    Returns: bool (True if companion is active)
    """
    c_id, c_data = companions.get_active_companion(app.save_data)
    
    if c_id:
        roster = companions.load_companion_roster()
        c_def = roster.get(c_id, {})
        c_lvl = c_data.get("level", 1)
        c_xp = c_data.get("xp", 0)
        
        # 1. Update Label
        app.depart_companion_lbl.config(text=f"{c_def['name']} (Lvl {c_lvl})")
        
        # 2. Calculate XP Bar Percentage
        curr_base = companions.LEVEL_XP_THRESHOLDS.get(c_lvl, 0)
        next_xp = companions.LEVEL_XP_THRESHOLDS.get(c_lvl + 1, 99999)
        
        if c_lvl >= 5: 
            pct = 1.0
        else:
            req = next_xp - curr_base
            prog = c_xp - curr_base
            pct = min(1.0, prog / req) if req > 0 else 0
            
        # 3. Draw Bar
        app.depart_comp_xp_canvas.pack(pady=2)
        w = 200
        app.depart_comp_xp_canvas.coords(app.depart_comp_xp_rect, 0, 0, int(w * pct), 6)
        return True
    else:
        app.depart_companion_lbl.config(text="Solo Raid")
        app.depart_comp_xp_canvas.pack_forget()
        return False


# ----------------------------------------------------------------------
# DEPARTING SCREEN
# ----------------------------------------------------------------------

def build_departing_screen(app, frame):
    """
    Simple screen shown while the app processes raid start logic.
    """
    # 0. Clean the slate to prevent clipping over town screen
    for w in frame.winfo_children(): w.destroy()

    # Centered Content
    center_frame = tk.Frame(frame, bg="#111111")
    center_frame.place(relx=0.5, rely=0.5, anchor="center")
    
    # 1. Text Update
    tk.Label(center_frame, text="departing...", fg="#00FF00", bg="#111111", font=("Courier", 30, "bold")).pack(pady=20)
    
    # 2. Location & Difficulty (NEW)
    app.depart_location_lbl = tk.Label(center_frame, text="Wasteland", fg="#FFFFFF", bg="#111111", font=("Courier", 14, "bold"))
    app.depart_location_lbl.pack(pady=5)
    
    # 3. Character & Companion Info Display
    app.depart_char_info_lbl = tk.Label(center_frame, text="", fg="#00FFFF", bg="#111111", font=("Courier", 11))
    app.depart_char_info_lbl.pack(pady=5)
    
    app.depart_companion_lbl = tk.Label(center_frame, text="", fg="#FFD700", bg="#111111", font=("Courier", 11))
    app.depart_companion_lbl.pack(pady=5)
    
    # Companion XP Bar
    app.depart_comp_xp_canvas = tk.Canvas(center_frame, width=200, height=6, bg="#333333", highlightthickness=0)
    app.depart_comp_xp_rect = app.depart_comp_xp_canvas.create_rectangle(0, 0, 0, 6, fill="#FFD700", width=0)
    # Pack managed dynamically
    
    # 4. Insured Gear Readout (NEW)
    app.depart_insurance_lbl = tk.Label(center_frame, text="", fg="#00FF00", bg="#111111", font=("Courier", 10, "italic"))
    app.depart_insurance_lbl.pack(pady=10)
    
    app.depart_status_lbl = tk.Label(center_frame, text="Initializing...", fg="#AAAAAA", bg="#111111", font=("Courier", 14))
    app.depart_status_lbl.pack(pady=10)
    
    tk.Label(center_frame, text="good luck wanderer.", fg="#005500", bg="#111111", font=("Courier", 12, "italic")).pack(pady=30)

def update_depart_status(app, text):
    """
    Updates status text and refreshes character/companion info from current save data.
    """
    if hasattr(app, 'depart_status_lbl') and app.depart_status_lbl.winfo_exists():
        app.depart_status_lbl.config(text=text)
        
        # Update Location & Difficulty
        loc_name = app.save_data.get("current_raid_location_name", "Unknown Location")
        diff = app.save_data.get("current_raid_difficulty", "Easy")
        
        col = "#00FF00"
        if diff == "Medium": col = "#FFFF00"
        elif diff == "Hard": col = "#FF4444"
        elif diff == "VeryHard": col = "#AA0000"
        
        if hasattr(app, 'depart_location_lbl'):
            app.depart_location_lbl.config(text=f"{loc_name} ({diff})", fg=col)
        
        # Update Char Stats (From Baseline)
        baseline = app.save_data.get("baseline", {})
        lvl = int(baseline.get("level", 1))
        hp = int(baseline.get("health", 0))
        char_txt = f"Player Lvl {lvl} | HP: {hp}"
        app.depart_char_info_lbl.config(text=char_txt)
        
        # Update Companion (Delegated)
        _draw_companion_xp_status(app)
        
        # Update Insurance Display (NEW)
        insured_list = app.save_data.get("insured_items", [])
        if insured_list:
            count = len(insured_list)
            # Fetch names for first few items to make it look nice
            game_path = app.save_data.get("game_install_path", "")
            char_data = inventory.get_character_data(game_path)
            inv = char_data.get("inventory", [])
            
            names = []
            for code in insured_list[:3]: # Limit to 3 names
                # Find item name in inventory
                match = next((i for i in inv if i["code"] == code), None)
                if match: names.append(match["name"])
            
            display_str = "Insured: " + ", ".join(names)
            if count > 3: display_str += f" (+{count-3} more)"
            app.depart_insurance_lbl.config(text=display_str)
        else:
            app.depart_insurance_lbl.config(text="")

        app.update_idletasks()

# ----------------------------------------------------------------------
# RAID END SCREEN
# ----------------------------------------------------------------------

def build_raid_end_screen(app, frame):
    """
    Summary screen displayed after Death or Extraction.
    """
    # 1. Header (Outcome)
    app.end_header_lbl = tk.Label(frame, text="", fg="#FFFFFF", bg="#111111", font=("Courier", 28, "bold"))
    app.end_header_lbl.pack(pady=(20, 10))
    
    # 2. Companion Summary (New)
    comp_frame = tk.Frame(frame, bg="#111111")
    comp_frame.pack(fill="x", padx=50, pady=5)
    
    app.end_comp_name_lbl = tk.Label(comp_frame, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.end_comp_name_lbl.pack()
    
    app.end_comp_xp_bar = tk.Canvas(comp_frame, width=300, height=8, bg="#333333", highlightthickness=0)
    app.end_comp_xp_rect = app.end_comp_xp_bar.create_rectangle(0, 0, 0, 8, fill="#FFD700", width=0)
    # Pack managed dynamically
    
    # 3. Stats Container
    app.end_stats_frame = tk.Frame(frame, bg="#111111")
    app.end_stats_frame.pack(fill="both", expand=True, padx=50, pady=10)
    
    # Create labels for standard stats
    app.end_stat_labels = {}
    stat_keys = ["duration", "tasks", "xp", "caps", "scrip", "loot_count"]
    
    for key in stat_keys:
        lbl = tk.Label(app.end_stats_frame, text="", fg="#CCCCCC", bg="#111111", font=("Courier", 14), anchor="w")
        lbl.pack(fill="x", pady=2)
        app.end_stat_labels[key] = lbl
        
    # Container for Item List (Extraction only)
    app.end_items_label = tk.Label(app.end_stats_frame, text="", fg="#00FF00", bg="#111111", font=("Courier", 10), justify="left")
    app.end_items_label.pack(fill="both", expand=True, pady=10)

    # 4. Footer / Action
    footer = tk.Frame(frame, bg="#111111")
    footer.pack(side="bottom", pady=20, fill="x")
    
    app.end_processing_lbl = tk.Label(footer, text="", fg="#FFFF00", bg="#111111", font=("Courier", 10, "bold"))
    app.end_processing_lbl.pack(pady=5)
    
    app.end_confirm_btn = tk.Button(footer, text="CONFIRM", command=lambda: _on_confirm_click(app), 
                                    bg="#333333", fg="#555555", font=("Courier", 16, "bold"), width=25, state="disabled")
    app.end_confirm_btn.pack(pady=10)


def animate_raid_end_sequence(app, context):
    """
    Orchestrates the fade-in of stats and triggers background logic execution.
    context: dict from etw_raid.prepare_*
    """
    # 1. Setup Header & Companion
    outcome = context.get("outcome", "RAID ENDED")
    
    # --- ERROR HANDLING BLOCK (NEW) ---
    if outcome == "ERROR":
        app.end_header_lbl.config(text="CONNECTION FAILED", fg="#FF0000")
        app.end_items_label.config(text=f"\nERROR: {context.get('message')}\n\nPlease verify Fallout 3 is running and unpaused.\nProgress has NOT been saved.")
        
        # Configure button for Retry
        app.end_confirm_btn.config(text="RETURN TO HUD", state="normal", bg="#550000", fg="#FFFFFF", command=lambda: app.show_game_screen())
        app.end_processing_lbl.config(text="SAFE TO RETRY", fg="#FFFF00")
        
        # Clear other stats
        for key in app.end_stat_labels:
            app.end_stat_labels[key].config(text="")
        return # STOP SEQUENCE
    # ----------------------------------

    col = "#00FF00" if outcome == "EXTRACTED" else ("#FF0000" if outcome == "KIA" else "#FFFF00")
    app.end_header_lbl.config(text=outcome, fg=col)
    
    # Companion Display
    c_data = context.get("companion")
    if c_data:
        app.end_comp_name_lbl.config(text=f"{c_data['name']} (Lvl {c_data['level']})")
        app.end_comp_xp_bar.pack(pady=5)
        w = 300
        app.end_comp_xp_bar.coords(app.end_comp_xp_rect, 0, 0, int(w * c_data['xp_pct']), 8)
    else:
        app.end_comp_name_lbl.config(text="")
        app.end_comp_xp_bar.pack_forget()

    # 2. Define Visual Steps
    # If KIA, we show 0s or empty for rewards
    steps = [
        ("duration", f"Time in Raid: {context.get('duration_str', '--:--')}", 500),
        ("tasks",    f"Contracts:    {context.get('tasks_str', '0')}", 1000)
    ]
    
    if outcome == "EXTRACTED":
        steps.extend([
            ("xp",       f"Experience:   {context.get('xp', 0)}", 1500),
            ("caps",     f"Caps Earned:  {context.get('caps', 0)}", 2000),
            ("scrip",    f"Scrip Earned: {context.get('scrip', 0)}", 2500),
            ("loot_count", f"Loot Secured: {context.get('loot_count', 0)} Items", 3000)
        ])
        
        # Build Item List String
        rewards = context.get("rewards_package", {})
        item_lines = []
        for it in rewards.get("items", []):
            name = it.get("name", "Unknown")
            qty = it.get("qty", 1)
            line = f"- {name}"
            if qty > 1: line += f" (x{qty})"
            if it.get("from_modifier"): line += " [BONUS]"
            item_lines.append(line)
            
        full_list = "\n".join(item_lines) if item_lines else "No items."
        app.after(3500, lambda: app.end_items_label.config(text=full_list))
        
    elif outcome == "KIA":
        # For KIA, we show "LOST" for potential rewards? Or just 0.
        # Spec says "fade in one line at a time as well".
        steps.extend([
            ("xp",       "Experience:   0 (LOST)", 1500),
            ("caps",     "Caps Earned:  0 (LOST)", 2000),
            ("scrip",    "Scrip Earned: 0 (LOST)", 2500),
            ("loot_count", "Loot Status:  COMPROMISED", 3000)
        ])
        app.end_items_label.config(text="Inventory requires sanitation.")

    # Schedule Visuals
    for key, txt, delay in steps:
        app.after(delay, lambda k=key, t=txt: _reveal_stat(app, k, t))
        
    # 3. Trigger Background Logic Sequence
    # This runs in parallel with visuals, managing the "Greyed Out" button state
    app.after(100, lambda: _start_background_process(app, context))


def _reveal_stat(app, key, text):
    if hasattr(app, 'end_stat_labels') and key in app.end_stat_labels:
        lbl = app.end_stat_labels[key]
        if lbl.winfo_exists():
            lbl.config(text=text)
            app.update_idletasks()

# ----------------------------------------------------------------------
# BACKGROUND PROCESS (POLLING)
# ----------------------------------------------------------------------

def _start_background_process(app, context):
    """
    Executes the clean-up steps sequentially using app.after() to avoid freezing the UI entirely
    while still enforcing the delay.
    """
    outcome = context.get("outcome")
    
    if outcome == "KIA":
        app.end_processing_lbl.config(text="STATUS: Scanning inventory for losses...")
        # Step 1: Scan
        app.after(500, lambda: _kia_step_1(app))
        
    elif outcome == "EXTRACTED":
        # Rewards were already sent/verified in Step 1 (Prepare)
        app.end_processing_lbl.config(text="STATUS: Syncing local records...")
        # Step 1: Sync Stub (Local JSON)
        app.after(500, lambda: _ext_step_1(app, context))

# --- KIA SEQUENCER ---
def _kia_step_1(app):
    # Execute Step 1 (Scan & Sync) - Has internal 2s delay
    raid.raid_cleanup.execute_death_step_1_scan(app.save_data)
    app.end_processing_lbl.config(text="STATUS: Removing lost items...")
    app.after(500, lambda: _kia_step_2(app))

def _kia_step_2(app):
    # Execute Step 2 (Losses) - Has internal 2s delay
    raid.raid_cleanup.execute_death_step_2_losses(app.save_data)
    app.end_processing_lbl.config(text="STATUS: Removing buffs...")
    app.after(500, lambda: _kia_step_3(app))

def _kia_step_3(app):
    # Execute Step 3 (Debuff) - Has internal 2s delay
    raid.raid_cleanup.execute_death_step_3_debuff(app.save_data)
    _enable_confirm(app)

# --- EXTRACTION SEQUENCER ---
def _ext_step_1(app, context):
    # Execute Step 1 (Local Sync Stub)
    # The actual commands were sent in the "Big Batch" in etw_raid.py
    # This step now just updates character_data.json
    raid.raid_cleanup.execute_extraction_step_1_rewards(app.save_data, context)
    
    app.end_processing_lbl.config(text="STATUS: Removing buffs...")
    app.after(500, lambda: _ext_step_2(app))

def _ext_step_2(app):
    # Execute Step 2 (Debuff) - Has internal 2s delay
    raid.raid_cleanup.execute_extraction_step_2_debuff(app.save_data)
    _enable_confirm(app)

# --- FINAL ENABLE ---
def _enable_confirm(app):
    if hasattr(app, 'end_confirm_btn') and app.end_confirm_btn.winfo_exists():
        app.end_confirm_btn.config(text="RETURN TO TOWN", state="normal", bg="#003300", fg="#00FF00", command=lambda: _on_confirm_click(app))
        app.end_processing_lbl.config(text="Ready to Return.", fg="#00FF00")
        if hasattr(app, 'end_tip_lbl'):
            app.end_tip_lbl.config(text="Transport coordinates locked.", fg="#00FF00")

def _on_confirm_click(app):
    # Trigger FINAL step: Teleport
    if hasattr(app, 'finalize_raid_end'):
        app.finalize_raid_end()