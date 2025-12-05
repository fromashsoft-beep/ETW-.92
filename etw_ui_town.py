import tkinter as tk

# Foundation
import etw_config as config
import etw_io as io

# Core & Systems
import etw_engine as engine
import etw_companions as companions
import etw_ui_quests
import etw_stats as stats

# ----------------------------------------------------------------------
# BUILDERS
# ----------------------------------------------------------------------

def build_town_screen(app, frame):
    """
    Constructs the entire Town Hub UI within the provided frame.
    """
    # 1. Header
    tk.Label(frame, text="Rustwater Outpost", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=(10, 5))
    
    app.town_day_label = tk.Label(frame, text="Day: 1", fg="#FFFFFF", bg="#111111", font=("Courier", 12))
    app.town_day_label.pack(pady=(0, 10))
    
    # Currency Frame (Top Right)
    curr_frame = tk.Frame(frame, bg="#111111")
    curr_frame.place(relx=0.98, rely=0.02, anchor="ne")
    
    app.town_scrip_label = tk.Label(curr_frame, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.town_scrip_label.pack(anchor="e")
    
    app.town_comps_label = tk.Label(curr_frame, text="", fg="#AAAAAA", bg="#111111", font=("Courier", 10))
    app.town_comps_label.pack(anchor="e")
    
    # 2. Main Navigation
    app.town_nav_frame = tk.Frame(frame, bg="#111111")
    app.town_nav_frame.pack(pady=5, fill="x")
    
    _refresh_nav_buttons(app)
        
    # 3. Debug Tools
    debug_frame = tk.Frame(frame, bg="#330000", bd=2, relief="ridge")
    debug_frame.pack(fill="x", padx=20, pady=5)
    
    tk.Label(debug_frame, text="DEBUG TOOLS (Town)", fg="#FF0000", bg="#330000", font=("Courier", 10, "bold")).pack(pady=2)
    
    d_row = tk.Frame(debug_frame, bg="#330000")
    d_row.pack(pady=5)
    
    tk.Button(d_row, text="Rep +1", command=lambda: run_town_debug(app, engine.debug_increase_rep, "Reputation Increased"), bg="#550000", fg="#FFFFFF", font=("Courier", 8)).pack(side="left", padx=5)
    tk.Button(d_row, text="Day +1", command=lambda: run_town_debug(app, engine.debug_advance_day, "Day Advanced"), bg="#550000", fg="#FFFFFF", font=("Courier", 8)).pack(side="left", padx=5)
    tk.Button(d_row, text="Unlock Hideout", command=lambda: run_town_debug(app, engine.debug_unlock_all_stations, "Hideout Unlocked"), bg="#550000", fg="#FFFFFF", font=("Courier", 8)).pack(side="left", padx=5)
    tk.Button(d_row, text="Comp Lvl +1", command=lambda: run_town_debug(app, engine.debug_level_up_companions, "Companions Leveled"), bg="#550000", fg="#FFFFFF", font=("Courier", 8)).pack(side="left", padx=5)
    tk.Button(d_row, text="Scrip +100", command=lambda: run_town_debug(app, engine.debug_add_scrip_100, "Scrip +100"), bg="#003300", fg="#FFFFFF", font=("Courier", 8)).pack(side="left", padx=5)
    
    tk.Button(d_row, text="Unlock Crew", command=lambda: run_town_debug(app, engine.debug_unlock_all_companions, "All Companions Unlocked"), bg="#003333", fg="#00FFFF", font=("Courier", 8)).pack(side="left", padx=5)
    
    app.town_debug_feedback_lbl = tk.Label(debug_frame, text="", fg="#00FF00", bg="#330000", font=("Courier", 9))
    app.town_debug_feedback_lbl.pack(pady=2)
    
    # 4. Task Board
    board_header = tk.Frame(frame, bg="#111111")
    board_header.pack(pady=(10, 0), padx=10, fill="x")
    
    tk.Label(board_header, text="Available Contracts", fg="#FFFFFF", bg="#111111", font=("Courier", 14, "bold")).pack(side="left")
    
    app.town_capacity_label = tk.Label(board_header, text="Active: 0/1", fg="#AAAAAA", bg="#111111", font=("Courier", 12))
    app.town_capacity_label.pack(side="right", padx=(10, 0))
    
    app.taskboard_error_label = tk.Label(board_header, text="", fg="#FF0000", bg="#111111", font=("Courier", 10, "bold"))
    app.taskboard_error_label.pack(side="right", padx=10)
    
    app.town_taskboard_frame = tk.Frame(frame, bg="#111111")
    app.town_taskboard_frame.pack(pady=(5, 0), padx=10, fill="both", expand=True)
    
    # 5. Bottom Controls (Homepoint, Threat, Raid)
    bottom_area = tk.Frame(frame, bg="#111111")
    bottom_area.pack(pady=10, fill="x")
    
    hp_frame = tk.Frame(bottom_area, bg="#111111")
    hp_frame.pack(pady=5)
    
    tk.Label(hp_frame, text="Homepoint:", fg="#888888", bg="#111111", font=("Courier", 9)).pack(side="left", padx=5)
    
    app.btn_hp_megaton = tk.Button(hp_frame, text="Megaton", command=lambda: set_homepoint(app, "Megaton"), width=10, font=("Courier", 8))
    app.btn_hp_megaton.pack(side="left", padx=2)
    
    app.btn_hp_tenpenny = tk.Button(hp_frame, text="Tenpenny", command=lambda: set_homepoint(app, "Tenpenny Tower"), width=10, font=("Courier", 8))
    app.btn_hp_tenpenny.pack(side="left", padx=2)
    
    app.btn_hp_rivet = tk.Button(hp_frame, text="Rivet City", command=lambda: set_homepoint(app, "Rivet City"), width=12, font=("Courier", 8))
    app.btn_hp_rivet.pack(side="left", padx=2)
    
    threat_cnt = tk.Frame(bottom_area, bg="#111111")
    threat_cnt.pack(pady=5)
    
    tk.Label(threat_cnt, text="Threat Level:", fg="#FF0000", bg="#111111", font=("Courier", 10, "bold")).pack(side="left")
    
    app.town_threat_canvas = tk.Canvas(threat_cnt, width=100, height=15, bg="#333333", highlightthickness=0)
    app.town_threat_canvas.pack(side="left", padx=5)
    app.town_threat_rect = app.town_threat_canvas.create_rectangle(0, 0, 0, 15, fill="#00FF00", width=0)
    
    # --- DIFFICULTY SELECTION ---
    tk.Label(bottom_area, text="choose your location", fg="#888888", bg="#111111", font=("Courier", 8, "italic")).pack(pady=(10, 2))
    
    app.town_diff_frame = tk.Frame(bottom_area, bg="#111111")
    app.town_diff_frame.pack(pady=2)
    
    app.btn_diff_easy = tk.Button(app.town_diff_frame, text="Easy", command=lambda: _select_difficulty(app, "Easy"), width=8, font=("Courier", 9, "bold"))
    app.btn_diff_easy.pack(side="left", padx=2)
    
    app.btn_diff_medium = tk.Button(app.town_diff_frame, text="Medium", command=lambda: _select_difficulty(app, "Medium"), width=8, font=("Courier", 9, "bold"))
    app.btn_diff_medium.pack(side="left", padx=2)
    
    app.btn_diff_hard = tk.Button(app.town_diff_frame, text="Hard", command=lambda: _select_difficulty(app, "Hard"), width=8, font=("Courier", 9, "bold"))
    app.btn_diff_hard.pack(side="left", padx=2)
    
    app.btn_diff_veryhard = tk.Button(app.town_diff_frame, text="Very Hard", command=lambda: _select_difficulty(app, "VeryHard"), width=10, font=("Courier", 9, "bold"))
    app.btn_diff_veryhard.pack(side="left", padx=2)
    # -----------------------------

    app.raid_condition_label = tk.Label(bottom_area, text="", fg="#00FFFF", bg="#111111", font=("Courier", 10))
    app.raid_condition_label.pack(pady=2)
    
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.raid_condition_label)
        
    app.raid_depart_btn = tk.Button(bottom_area, text="Depart on Raid", command=app.start_raid, bg="#003300", fg="#00FF00", font=("Courier", 14, "bold"), width=20, pady=5)
    app.raid_depart_btn.pack(pady=10)
    
    app.companion_footer_label = tk.Label(bottom_area, text="", fg="#00FF00", bg="#111111", font=("Courier", 10, "bold"))
    app.companion_footer_label.pack(pady=5)

def _refresh_nav_buttons(app):
    for w in app.town_nav_frame.winfo_children(): w.destroy()
    
    buttons = [
        ("Quest Log", app.show_quest_log_screen, "CHECK_MAIN"),
        ("Stop n' Shop", app.show_shop_screen, "CAT_SHOP"),
        ("The Salty Atom", app.show_bar_screen, "CAT_BAR"),
        ("Super Duper Shelter", app.show_hideout_screen, "CAT_HIDEOUT"),
        ("Inventory", app.show_inventory_screen, None),
        ("Info", app.show_character_info_screen, None)
    ]
    
    for i, (tx, cm, q_tag) in enumerate(buttons):
        bg_col = "#222222"
        fg_col = "#00FFFF"
        
        if q_tag:
            if _is_category_ready_to_turn_in(app, q_tag):
                bg_col = "#004400"
                fg_col = "#00FF00"
        
        tk.Button(app.town_nav_frame, text=tx, command=cm, bg=bg_col, fg=fg_col, font=("Courier", 10)).grid(row=0, column=i, padx=5, sticky="ew")
        app.town_nav_frame.columnconfigure(i, weight=1)

def _is_category_ready_to_turn_in(app, category):
    active_quests = app.save_data.get("active_side_quests", [])
    
    def _check_quest_done(q_id):
        prog = app.save_data.get("quest_progress", {}).get(q_id, [])
        return len(prog) > 0 and all(prog)

    if category == "CHECK_MAIN":
        mq_idx = app.save_data.get("current_main_quest_index", 0)
        if mq_idx < len(app.main_quests):
            curr_q = app.main_quests[mq_idx]
            q_code = curr_q.get("id", "main")
            if _check_quest_done(q_code): return True
        return False

    if category == "CAT_SHOP":
        if "shop_unlock" in active_quests and _check_quest_done("shop_unlock"): return True
        if "insurance_unlock" in active_quests and _check_quest_done("insurance_unlock"): return True
        
    if category == "CAT_BAR":
        if "bar_unlock" in active_quests:
            if stats.compute_reputation(app.save_data) >= 1.0: return True
        for q_id in active_quests:
            if q_id.startswith("recruitment_") and _check_quest_done(q_id): return True
            
    if category == "CAT_HIDEOUT":
        if "hideout_unlock" in active_quests and _check_quest_done("hideout_unlock"): return True
        for q_id in active_quests:
            if q_id.startswith("loyalty_") and _check_quest_done(q_id): return True
            
    return False

# ----------------------------------------------------------------------
# UPDATERS & HELPERS
# ----------------------------------------------------------------------

def update_town_stats(app):
    """
    Refreshes all dynamic labels in the Town Screen.
    """
    if hasattr(app, 'town_scrip_label'):
        app.town_scrip_label.config(text=f"Scrip: {app.save_data.get('scrip', 0)}")
        
    if hasattr(app, 'town_comps_label'):
        comps = app.save_data.get('components', 0)
        app.town_comps_label.config(text=f"Components: {comps}")
        
    day = app.save_data.get("day_cycle", 1)
    if hasattr(app, 'town_day_label'):
        app.town_day_label.config(text=f"Day: {day}")
        
    threat = app.save_data.get("threat_level", 1)
    if hasattr(app, 'town_threat_canvas'):
        w = 100
        pct = min(1.0, threat / 5.0)
        app.town_threat_canvas.coords(app.town_threat_rect, 0, 0, int(w * pct), 15)
        
        col = "#00FF00"
        if threat >= 3: col = "#FFFF00"
        if threat >= 5: col = "#FF0000"
        app.town_threat_canvas.itemconfig(app.town_threat_rect, fill=col)
        
    active_count = len([t for t in app.save_data.get("tasks", []) if t.get("state") == "pending"])
    cap = app.save_data.get("unlocked_task_slots", 1)
    if hasattr(app, 'town_capacity_label'):
        app.town_capacity_label.config(text=f"Active: {active_count}/{cap}")
        
    update_homepoint_ui(app)
    update_difficulty_ui(app)
    update_companion_footer(app)
    update_raid_condition_labels(app)
    
    if hasattr(app, 'town_nav_frame'):
        _refresh_nav_buttons(app)
    
    if hasattr(app, 'town_taskboard_frame'):
        etw_ui_quests.refresh_taskboard_ui(app, app.town_taskboard_frame)

def set_homepoint(app, loc):
    app.save_data["homepoint"] = loc
    engine.save_save_data(app.save_data)
    update_homepoint_ui(app)

def update_homepoint_ui(app):
    curr = app.save_data.get("homepoint", "Megaton")
    
    def _style(btn, name):
        if not btn: return
        if name == curr: 
            btn.config(bg="#004400", fg="#00FF00", relief="sunken")
        else: 
            btn.config(bg="#222222", fg="#555555", relief="raised")
            
    if hasattr(app, 'btn_hp_megaton'):
        _style(app.btn_hp_megaton, "Megaton")
        _style(app.btn_hp_tenpenny, "Tenpenny Tower")
        _style(app.btn_hp_rivet, "Rivet City")

def _select_difficulty(app, diff):
    rep = stats.compute_reputation(app.save_data)
    allowed = True
    if diff == "Medium" and rep < 2: allowed = False
    elif diff == "Hard" and rep < 4: allowed = False
    elif diff == "VeryHard" and rep < 6: allowed = False
    
    if allowed:
        app.save_data["raid_difficulty_selection"] = diff
        engine.save_save_data(app.save_data)
        update_difficulty_ui(app)

def update_difficulty_ui(app):
    current = app.save_data.get("raid_difficulty_selection", "Easy")
    rep = stats.compute_reputation(app.save_data)
    
    configs = [
        (app.btn_diff_easy, "Easy", 0, "#00FF00"),
        (app.btn_diff_medium, "Medium", 2, "#FFFF00"),
        (app.btn_diff_hard, "Hard", 4, "#FF4444"),
        (app.btn_diff_veryhard, "VeryHard", 6, "#AA0000")
    ]
    
    for btn, key, req_rep, act_col in configs:
        if not btn: continue
        is_locked = rep < req_rep
        is_selected = (current == key)
        
        if is_locked:
            btn.config(state="disabled", bg="#111111", fg="#444444", relief="flat", text=f"{key}\n(Lck)")
        else:
            btn.config(state="normal", text=key)
            if is_selected:
                btn.config(bg=act_col, fg="#000000", relief="sunken")
            else:
                btn.config(bg="#222222", fg=act_col, relief="raised")

def update_companion_footer(app):
    if not hasattr(app, 'companion_footer_label'): return
    
    c_id, c_data = companions.get_active_companion(app.save_data)
    if c_id:
        roster = companions.load_companion_roster()
        c_def = roster.get(c_id, {})
        buff_name = c_def.get('base_buff_type', '').replace("_", " ").title()
        txt = f"Active Companion: {c_def.get('name')} (Lvl {c_data['level']} {buff_name})"
        app.companion_footer_label.config(text=txt)
    else:
        app.companion_footer_label.config(text="Active Companion: None")

def update_raid_condition_labels(app):
    mod_id = app.save_data.get("current_raid_modifier", "")
    
    if not mod_id:
        txt = "Condition: Clear Skies"
    else:
        conf = io.load_json(config.PATHS["content_raids"])
        mod_data = conf.get("raid_modifiers", {}).get(mod_id, {})
        name = mod_data.get("name", "Unknown")
        desc = mod_data.get("description", "")
        txt = f"{name}: {desc}"
    
    if hasattr(app, 'raid_condition_label'):
        app.raid_condition_label.config(text=txt)
    
    if hasattr(app, 'raid_condition_raid_label') and app.raid_condition_raid_label.winfo_exists():
        app.raid_condition_raid_label.config(text=txt)

# ----------------------------------------------------------------------
# DEBUG
# ----------------------------------------------------------------------

def run_town_debug(app, func, msg):
    """
    Executes a debug function from the Engine and shows feedback.
    """
    func(app.save_data)
    app.show_temporary_text(app.town_debug_feedback_lbl, msg, "#00FF00")
    update_town_stats(app)