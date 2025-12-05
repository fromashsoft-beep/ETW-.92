import tkinter as tk
import time
import random

# Foundation
import etw_config as config
import etw_io as io

# Core & Systems
import etw_engine as engine
import etw_companions as companions
import etw_ambush as ambush
import etw_ui_quests
import etw_task_logic as task_logic

# ----------------------------------------------------------------------
# BUILDERS
# ----------------------------------------------------------------------

def build_game_screen(app, frame):
    """
    Constructs the Active Raid HUD.
    """
    # 1. Companion Status & Ultimate Bar
    app.raid_active_companion_display = tk.Label(frame, text="Active Companion: None", fg="#00FF00", bg="#111111", font=("Courier", 10, "bold"))
    app.raid_active_companion_display.pack(pady=(10, 5))
    
    app.raid_ult_bar_canvas = tk.Canvas(frame, width=200, height=8, bg="#333333", highlightthickness=0)
    app.raid_ult_bar_canvas.pack(pady=2)
    app.raid_ult_rect = app.raid_ult_bar_canvas.create_rectangle(0, 0, 0, 8, fill="#00FFFF", width=0)
    
    app.raid_ult_btn = tk.Button(frame, text="ULTIMATE READY", command=lambda: trigger_companion_ultimate(app), bg="#00FFFF", fg="#000000", font=("Courier", 8, "bold"))
    
    # 2. Raid Condition (Modifier)
    app.raid_condition_raid_label = tk.Label(frame, text="", fg="#00FFFF", bg="#111111", font=("Courier", 10))
    app.raid_condition_raid_label.pack(pady=(10, 5)) 
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.raid_condition_raid_label)
        
    # 3. Threat Meter
    threat_f = tk.Frame(frame, bg="#111111")
    threat_f.pack(pady=5)
    tk.Label(threat_f, text="Threat:", fg="#FF0000", bg="#111111", font=("Courier", 10, "bold")).pack(side="left")
    
    app.raid_threat_canvas = tk.Canvas(threat_f, width=200, height=15, bg="#333333", highlightthickness=0)
    app.raid_threat_canvas.pack(side="left", padx=5)
    app.raid_threat_rect = app.raid_threat_canvas.create_rectangle(0, 0, 0, 15, fill="#00FF00", width=0)
    
    # 4. Timer & Pause
    timer_box = tk.Frame(frame, bg="#111111")
    timer_box.pack(pady=5)
    
    app.raid_timer_label = tk.Label(timer_box, text="Raid time: --:--", fg="#00FFFF", bg="#111111", font=("Courier", 12, "bold"))
    app.raid_timer_label.pack(side="left")
    
    app.raid_pause_button = tk.Button(timer_box, text="Pause", command=lambda: toggle_raid_pause(app), bg="#222222", fg="#00FFFF", font=("Courier", 10))
    app.raid_pause_button.pack(side="left", padx=10)
    
    # 5. Active Buffs List
    app.active_buffs_label = tk.Label(frame, text="", fg="#00FFFF", bg="#111111", font=("Courier", 10), justify="left")
    app.active_buffs_label.pack(pady=2, fill="x", padx=10)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.active_buffs_label)
        
    # 6. Extraction Points
    app.extract_frame = tk.Frame(frame, bg="#111111")
    app.extract_frame.pack(pady=5)
    
    # 7. Action Controls
    ctrl = tk.Frame(frame, bg="#111111")
    ctrl.pack(pady=10)
    
    app.died_button = tk.Button(ctrl, text="DIED", command=lambda: app.handle_death(), bg="#550000", fg="#FFFFFF", font=("Courier", 12, "bold"), width=12, pady=5)
    app.died_button.pack(side="left", padx=10)
    
    # SOS Button Initialization
    inv = app.save_data.get("inventory", {})
    sos_count = inv.get("sos_flare", 0)
    sos_text = "SOS Flare <25min timer>" if sos_count > 0 else "SOS <0>"
    
    app.sos_button = tk.Button(ctrl, text=sos_text, command=lambda: app.use_sos_flare(), bg="#AA5500", fg="#FFFFFF", font=("Courier", 10, "bold"), width=20, pady=5, state="disabled")
    app.sos_button.pack(side="left", padx=10)
    
    app.extracted_button = tk.Button(ctrl, text="EXTRACTED", command=lambda: app.handle_extraction(), bg="#003355", fg="#00FFFF", font=("Courier", 12, "bold"), width=12, pady=5)
    app.extracted_button.pack(side="left", padx=10)
    
    # 8. System Controls (Debug)
    sys_row = tk.Frame(frame, bg="#111111")
    sys_row.pack(pady=5)
    
    tk.Button(sys_row, text="[+10 Min]", command=lambda: debug_add_time(app, 600), bg="#333333", fg="#FFFFFF", font=("Courier", 8)).pack(side="left", padx=5)
    app.debug_raid_time_btn = tk.Button(sys_row, text="[+30 Min Raid]", command=lambda: debug_add_time(app, 1800), bg="#550000", fg="#FFFFFF", font=("Courier", 8))
    app.debug_raid_time_btn.pack(side="left", padx=5)
    
    # UPDATED DEBUG BUTTON: Now uses the new ambush logic
    tk.Button(sys_row, text="[Trigger Ambush]", command=lambda: debug_trigger_ambush(app), bg="#550000", fg="#FFFFFF", font=("Courier", 8)).pack(side="left", padx=5)
    
    # 9. Quest HUD Containers
    # Combined Pager for Main + Side Quests
    app.main_quest_frame = tk.Frame(frame, bg="#111111")
    app.main_quest_frame.pack(pady=5, fill="x", padx=10)
    
    # Contracts (Tasks) List
    app.task_frame = tk.Frame(frame, bg="#111111")
    app.task_frame.pack(pady=5, fill="x", padx=10)

    # 10. Save & Quit (Bottom Right)
    # Using pack(side=bottom, anchor=e) relative to the main frame, 
    # but since everything else is packed top-down, we put it at the very bottom.
    bottom_frame = tk.Frame(frame, bg="#111111")
    bottom_frame.pack(side="bottom", fill="x", pady=10, padx=10)
    
    tk.Button(bottom_frame, text="Save & Quit", command=lambda: save_and_quit_raid(app), bg="#000044", fg="#AAAAAA", font=("Courier", 8)).pack(side="right")

# ----------------------------------------------------------------------
# CLICK HANDLERS (Local wrappers to force refresh)
# ----------------------------------------------------------------------

def _handle_task_tick(app, task, idx):
    """
    Calls the logic to update data, then immediately forces a UI redraw.
    """
    # 1. Update Data
    task_logic.tick_dynamic_task_objective(app, task, idx, is_quest=False)
    
    # 2. Force UI Refresh immediately
    refresh_pending_tasks_game(app, app.task_frame)
    refresh_raid_quest_hud(app, app.main_quest_frame)

def _handle_quest_tick(app, quest, idx):
    # 1. Update Data
    task_logic.tick_dynamic_task_objective(app, quest, idx, is_quest=True)
    
    # 2. Force UI Refresh
    refresh_raid_quest_hud(app, app.main_quest_frame)

def _handle_static_quest_tick(app, qid, idx):
    # 1. Update Data
    task_logic.tick_static_quest_objective(app, qid, idx)
    
    # 2. Force UI Refresh
    refresh_raid_quest_hud(app, app.main_quest_frame)

# ----------------------------------------------------------------------
# QUEST HUD (PAGINATED: Main + All Side Quests)
# ----------------------------------------------------------------------

def refresh_raid_quest_hud(app, frame):
    """
    Combines Main Quest, Static Side Quests, and Dynamic Side Quests 
    into one paginated list (3 per page) for the Raid HUD.
    """
    for w in frame.winfo_children(): w.destroy()
    
    all_quests = []
    
    # 1. Main Quest
    mq_idx = app.save_data.get("current_main_quest_index", 0)
    if mq_idx < len(app.main_quests):
        all_quests.append({"type": "MAIN", "data": app.main_quests[mq_idx]})
        
    # 2. Side Quests (Static & Dynamic)
    active_side_ids = app.save_data.get("active_side_quests", [])
    
    def _find_quest_data(q_id):
        for sq in app.side_quests:
            if sq["id"] == q_id: return sq
        for dq in app.save_data.get("generated_side_quests", []):
            if dq["id"] == q_id: return dq
        return None

    for q_id in active_side_ids:
        q_data = _find_quest_data(q_id)
        if q_data:
            all_quests.append({"type": "SIDE", "data": q_data})
            
    if not all_quests:
        tk.Label(frame, text="No Active Quests", fg="#555555", bg="#111111", font=("Courier", 10)).pack()
        return

    # 3. Pagination Logic
    qpp = 3 
    total_pages = max(1, (len(all_quests) + qpp - 1) // qpp)
    
    if not hasattr(app, "quest_display_page"): app.quest_display_page = 0
    app.quest_display_page = max(0, min(total_pages - 1, app.quest_display_page))
    
    # 4. Render Header / Controls
    hdr = tk.Frame(frame, bg="#111111")
    hdr.pack(fill="x", pady=2)
    
    state_prev = "normal" if app.quest_display_page > 0 else "disabled"
    tk.Button(hdr, text="<", command=lambda: _cycle_raid_page(app, frame, -1), state=state_prev, bg="#333333", fg="#FFFFFF", font=("Courier", 8, "bold"), width=3).pack(side="left")
    
    tk.Label(hdr, text=f"Mission Log ({app.quest_display_page + 1}/{total_pages})", fg="#AAAAAA", bg="#111111", font=("Courier", 9)).pack(side="left", expand=True)
    
    state_next = "normal" if app.quest_display_page < total_pages - 1 else "disabled"
    tk.Button(hdr, text=">", command=lambda: _cycle_raid_page(app, frame, 1), state=state_next, bg="#333333", fg="#FFFFFF", font=("Courier", 8, "bold"), width=3).pack(side="right")
    
    # 5. Render Quests for Page
    start_idx = app.quest_display_page * qpp
    page_items = all_quests[start_idx : start_idx + qpp]
    
    for item in page_items:
        _create_raid_quest_widget(app, frame, item["data"], item["type"])

def _cycle_raid_page(app, frame, direction):
    app.quest_display_page += direction
    refresh_raid_quest_hud(app, frame)

def _create_raid_quest_widget(app, parent, quest, q_type):
    bg = "#222222"
    border_col = "#FFD700" if q_type == "MAIN" else "#00BFFF"
    
    f = tk.Frame(parent, bg=bg, bd=2, relief="solid", highlightbackground=border_col, highlightthickness=1)
    f.pack(fill="x", pady=4, padx=5)
    
    h = tk.Frame(f, bg=bg)
    h.pack(fill="x", pady=2)
    
    title_text = quest.get("title", "Quest")
    tk.Label(h, text=f"{q_type}: {title_text}", fg=border_col, bg=bg, font=("Courier", 10, "bold")).pack(anchor="w", padx=5)
    
    objs = quest.get("objectives", [])
    raw_objs = quest.get("raw_objectives", [])
    
    q_id = quest.get("id", "main")
    
    count = max(len(objs), len(raw_objs))
    
    for i in range(count):
        txt = objs[i] if i < len(objs) else "Objective"
        is_done = False
        
        prog_list = app.save_data.get("quest_progress", {}).get(str(q_id), [])
        if i < len(prog_list): is_done = prog_list[i]
        
        display_txt = txt
        show_tick = False
        
        if raw_objs and i < len(raw_objs):
            r_data = raw_objs[i]
            cur = r_data[3]
            tgt = r_data[4]
            is_done = (cur <= 0)
            
            if not is_done and tgt > 1:
                display_txt = f"{txt} [{cur}/{tgt}]"
            
            if not is_done: show_tick = True
            
        else:
            lower_obj = txt.lower()
            is_automated = "reach" in lower_obj or "have" in lower_obj or "acquire" in lower_obj or "reputation" in lower_obj
            if not is_done and not is_automated: show_tick = True

        fg = "#FFFFE0" if not is_done else "#555555"
        font_style = ("Courier", 9) if not is_done else ("Courier", 9, "overstrike")
        
        row = tk.Frame(f, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        row.columnconfigure(1, weight=1)
        
        tk.Label(row, text="➤", fg=fg, bg=bg, font=font_style, width=2).grid(row=0, column=0, sticky="n")
        tk.Label(row, text=display_txt, fg=fg, bg=bg, font=font_style, wraplength=app.current_wrap_width-80, justify="left").grid(row=0, column=1, sticky="w")
        
        if show_tick:
            cmd = None
            if raw_objs:
                # FIX: Use local wrapper
                cmd = lambda q=quest, idx=i: _handle_quest_tick(app, q, idx)
            else:
                # FIX: Use local wrapper
                cmd = lambda qid=q_id, idx=i: _handle_static_quest_tick(app, qid, idx)
                
            tk.Button(row, text="✓", command=cmd, bg="#004400", fg="#00FF00", bd=1, font=("Courier", 7), width=2).grid(row=0, column=2, sticky="e")

# ----------------------------------------------------------------------
# CONTRACTS (TASKS) HUD
# ----------------------------------------------------------------------

def refresh_pending_tasks_game(app, frame):
    """
    Renders only Contracts (Tasks) in the bottom list.
    """
    for w in frame.winfo_children(): w.destroy()
    
    active_tasks = [t for t in app.save_data.get("tasks", []) if t.get("state") == "pending"]
    active_tasks.sort(key=lambda x: not x.get("is_emergency", False))
    
    if not active_tasks:
        tk.Label(frame, text="No active contracts", fg="#555555", bg="#111111", font=("Courier", 10)).pack()
        return
        
    for task in active_tasks:
        _create_raid_task_widget(app, frame, task)

def _create_raid_task_widget(app, parent, task):
    is_emergency = task.get("is_emergency", False)
    bg = "#330000" if is_emergency else "#222222" 
    diff = task.get("difficulty", "easy")
    bd_col = "#444444"
    title_col = "#00FF00"
    if diff == "medium": bd_col = "#888800"; title_col = "#FFFF00"
    elif diff == "hard": bd_col = "#880000"; title_col = "#FF4444"
    if is_emergency: bd_col = "#FF0000"; title_col = "#FF4444"
    
    f = tk.Frame(parent, bg=bg, bd=2, relief="solid", highlightbackground=bd_col, highlightthickness=1)
    f.pack(fill="x", pady=4, padx=5)
    h = tk.Frame(f, bg=bg)
    h.pack(fill="x", pady=2)
    
    title_text = task['name']
    if is_emergency: title_text = f"🚨 {title_text}"
    cycle_txt = f"[{task.get('cycles_remaining', '?')} Days]"
    lbl = tk.Label(h, text=f"{title_text} {cycle_txt}", fg=title_col, bg=bg, font=("Courier", 11, "bold"))
    lbl.pack(side="left", padx=5)
    tags = task.get("tags", [])
    if tags: etw_ui_quests.create_tooltip(lbl, "Tags: " + ", ".join(tags))
    if task.get("ready_to_complete"):
        tk.Label(h, text="(Extract to Complete)", fg="#00FF00", bg=bg, font=("Courier", 9, "bold")).pack(side="right", padx=5)
    
    def _get_col(txt, base, done):
        if done: return "#555555"
        if "BONUS:" in txt: return "#FFFFFF"
        return base

    for idx, obj_data in enumerate(task.get("objectives", [])):
        icon, txt, col, cur, tgt = obj_data
        is_done = (cur <= 0)
        
        display_txt = txt
        if not is_done and tgt > 1:
            display_txt = f"{txt} [{cur}/{tgt}]"
        elif is_done:
            display_txt = f"{txt} (Done)"
            
        font_style = ("Courier", 10, "overstrike") if is_done else ("Courier", 10)
        fg_col = _get_col(txt, col, is_done)
        
        row = tk.Frame(f, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        row.columnconfigure(1, weight=1)
        tk.Label(row, text=icon, fg=fg_col, bg=bg, font=font_style, width=3, anchor="center").grid(row=0, column=0, sticky="n")
        wrap_w = max(200, app.current_wrap_width - 100)
        tk.Label(row, text=display_txt, fg=fg_col, bg=bg, font=font_style, wraplength=wrap_w, justify="left").grid(row=0, column=1, sticky="w")
        
        is_automated = False
        lower_txt = txt.lower()
        if "reach" in lower_txt or "have" in lower_txt or "acquire" in lower_txt:
            is_automated = True
            
        if not is_done and not task.get("ready_to_complete") and not is_automated:
            # FIX: Use local wrapper _handle_task_tick to force UI update
            tk.Button(row, text="✓", command=lambda t=task, i=idx: _handle_task_tick(app, t, i), bg="#004400", fg="#00FF00", bd=1, font=("Courier", 8), width=2).grid(row=0, column=2, sticky="e", padx=5)

# ----------------------------------------------------------------------
# UPDATERS & STATE
# ----------------------------------------------------------------------

def update_companion_raid_hud(app):
    """
    Updates the Companion Info and Ultimate Bar based on raid progress.
    """
    c_id, c_data = companions.get_active_companion(app.save_data)
    
    if c_id:
        roster = companions.load_companion_roster()
        c_def = roster.get(c_id, {})
        buff_name = c_def.get('base_buff_type', '').replace("_", " ").title()
        
        level = c_data.get('level', 1)
        base_pct = companions.BUFF_SCALING.get(level, 0.02)
        if c_data.get('loyalty_completed'): 
            base_pct += 0.05
            
        txt = f"Active Companion: {c_def.get('name')} | Lvl {level} | {buff_name} +{int(base_pct*100)}%"
        
        if level >= 5 and c_data.get('loyalty_completed'):
            prog = c_data.get('ultimate_progress', 0.0)
            prog_pct = int(prog * 100)
            txt += f" | Ult: {prog_pct}%"
            
            app.raid_ult_bar_canvas.pack(pady=2)
            w = 200
            app.raid_ult_bar_canvas.coords(app.raid_ult_rect, 0, 0, int(w * prog), 8)
            
            if prog >= 1.0:
                app.raid_ult_btn.pack(pady=2)
            else:
                app.raid_ult_btn.pack_forget()
        else:
            app.raid_ult_bar_canvas.pack_forget()
            app.raid_ult_btn.pack_forget()
            
        app.raid_active_companion_display.config(text=txt, fg="#00FF00")
    else:
        app.raid_active_companion_display.config(text="Active Companion: None", fg="#AAAAAA")
        app.raid_ult_bar_canvas.pack_forget()
        app.raid_ult_btn.pack_forget()

def refresh_extractions(app):
    for w in app.extract_frame.winfo_children(): w.destroy()
    ex = app.save_data.get("current_extractions", [])
    line = "  |  ".join(ex) if ex else "None"
    full_text = f"Extraction Points:  {line}"
    l = tk.Label(app.extract_frame, text=full_text, fg="#00FF00", bg="#111111", font=("Courier", 11, "bold"), justify="center")
    l.pack(pady=2, padx=10)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(l)

def update_active_buffs_display_raid(app):
    buffs = app.save_data.get("active_buffs", [])
    if buffs:
        txt = "Buffs: " + ", ".join([b.get("name", "Buff") for b in buffs])
        app.active_buffs_label.config(text=txt)
    else:
        app.active_buffs_label.config(text="")

# ----------------------------------------------------------------------
# ACTIONS
# ----------------------------------------------------------------------

def trigger_companion_ultimate(app):
    c_id, c_data = companions.get_active_companion(app.save_data)
    if c_id and c_data.get("ultimate_progress", 0.0) >= 1.0:
        if c_data.get("loyalty_completed"):
            c_data["ultimate_progress"] = 0.0
            # FIX: Use IO saving
            io.save_json(config.PATHS["save_data"], app.save_data)
            update_companion_raid_hud(app)
            app.show_temporary_text(app.raid_active_companion_display, "ULTIMATE ACTIVATED!", "#FFFFFF")
        else:
            app.show_temporary_text(app.raid_active_companion_display, "Loyalty Quest Required!", "#FF0000")

def toggle_raid_pause(app):
    is_paused = app.save_data.get("raid_paused", False)
    if is_paused:
        now = time.time()
        pause_start = app.save_data.get("raid_pause_start_timestamp", now)
        diff = now - pause_start
        app.save_data["raid_paused_elapsed"] = app.save_data.get("raid_paused_elapsed", 0.0) + diff
        app.save_data["raid_paused"] = False
        app.raid_pause_button.config(text="Pause")
    else:
        app.save_data["raid_paused"] = True
        app.save_data["raid_pause_start_timestamp"] = time.time()
        app.raid_pause_button.config(text="Resume")
    # FIX: Use IO saving
    io.save_json(config.PATHS["save_data"], app.save_data)

def save_and_quit_raid(app):
    """
    Saves the current raid state and closes the application.
    Allows for mid-raid interruptions without loss.
    """
    # 1. Update timestamp one last time
    import etw_game_timer as game_timer
    game_timer.process_game_tick(app.save_data)
    
    # 2. Force Save
    if io.save_json(config.PATHS["save_data"], app.save_data):
        print("Raid State Saved. Closing...")
        app.destroy()
    else:
        app.show_temporary_text(app.raid_timer_label, "SAVE FAILED! DO NOT QUIT!", "#FF0000")

# ----------------------------------------------------------------------
# DEBUG
# ----------------------------------------------------------------------

def debug_add_time(app, seconds):
    if app.save_data.get("raid_active"):
        app.save_data["last_raid_start_timestamp"] -= seconds
        io.save_json(config.PATHS["save_data"], app.save_data)
        if seconds >= 1800:
            app.show_temporary_text(app.raid_timer_label, "DEBUG: +30 MINUTES", "#FFFF00")

def debug_trigger_ambush(app):
    # REFACTORED: Use the new robust ambush logic via the main App controller if possible,
    # or simulate the flag trigger.
    if not app.save_data.get("raid_active"): return
    
    # Set the flag on the logic side (optional, but clean)
    # OR directly call the App's handler logic if we want immediate effect.
    
    # Let's force the app to think an ambush triggered in the timer loop
    # We can do this by manually calling the handler logic that ETW_App uses.
    
    ambush_data = ambush.prepare_ambush_coords(app.save_data)
    if ambush_data:
        app.show_temporary_text(app.raid_condition_raid_label, "DEBUG: AMBUSH TRIGGERED!", "#FF00FF")
        # Immediate execution for debug
        ambush.execute_ambush_spawn(app.save_data, ambush_data)
    else:
        app.show_temporary_text(app.raid_condition_raid_label, "Ambush Failed (No Coords)", "#FFFF00")