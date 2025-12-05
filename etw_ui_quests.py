import tkinter as tk
import re

# Foundation
import etw_config as config
import etw_io as io

# Core & Systems
import etw_engine as engine
import etw_tasks as tasks 
import etw_task_logic as task_logic
import etw_companions as companions 
import etw_ui_styles # Shared UI Utilities

# Note: etw_ui_town import removed from top-level to prevent circular dependency

# ----------------------------------------------------------------------
# HELPER: Color Logic
# ----------------------------------------------------------------------
def _get_objective_color(text, original_col, is_struck):
    if is_struck: return "#555555"
    if "BONUS:" in text:
        # FIX: Use IO/Config here
        conf = io.load_json(config.PATHS["content_tasks"])
        cols = conf.get("icon_colors", {})
        low = text.lower()
        if "slay" in low: return cols.get("slay", "#FF4444")
        if "retrieve" in low: return cols.get("retrieve", "#FFFF00")
        if "plant" in low: return cols.get("plant", "#00BFFF")
        if "clear" in low: return cols.get("clear", "#FFFFFF")
        return "#FFFFFF"
    return original_col

# ----------------------------------------------------------------------
# HELPER: Progress Check (Robust)
# ----------------------------------------------------------------------
def _is_quest_objective_done(app, q_id, obj_idx):
    """
    Checks if a specific objective index is marked complete.
    Handles str/int ID conversion safely.
    """
    if "quest_progress" not in app.save_data: return False
    
    # Always cast ID to string for JSON key lookup
    key = str(q_id)
    prog = app.save_data["quest_progress"].get(key, [])
    
    if obj_idx < len(prog): return prog[obj_idx]
    return False

def _tick_quest_obj(app, q_id, obj_idx):
    """
    FOR STATIC QUESTS ONLY: Marks a specific objective as complete.
    Delegates to new logic file.
    """
    task_logic.tick_static_quest_objective(app, q_id, obj_idx)


# ----------------------------------------------------------------------
# QUEST LOG SCREEN (Full UI)
# ----------------------------------------------------------------------
def build_quest_log_screen(app, frame):
    """
    Constructs the Quest Log UI, delegating active task/quest display.
    """
    # 1. Header (Top)
    tk.Label(frame, text="Quest Log", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=5)

    # 2. Navigation Bar (Underneath Header)
    nav = tk.Frame(frame, bg="#111111")
    nav.pack(fill="x", pady=5, padx=20)
    
    # Return Button (Left)
    tk.Button(nav, text="Return to Town", command=app.show_town_screen, bg="#003300", fg="#00FF00", font=("Courier", 12, "bold")).pack(side="left")
    
    # Scrip Display (Right)
    app.quest_log_scrip_label = tk.Label(nav, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.quest_log_scrip_label.pack(side="right")
    
    # 3. Main Content
    tk.Label(frame, text="Current Quests", fg="#FFD700", bg="#111111", font=("Courier", 14, "bold"), anchor="w").pack(fill="x", padx=20, pady=(10, 0))
    app.quest_log_quests_frame = tk.Frame(frame, bg="#111111")
    app.quest_log_quests_frame.pack(fill="x", padx=20, pady=5)

    tk.Label(frame, text="Active Contracts", fg="#00FFFF", bg="#111111", font=("Courier", 14, "bold"), anchor="w").pack(fill="x", padx=20, pady=(20, 0))
    app.quest_log_active_frame = tk.Frame(frame, bg="#111111")
    app.quest_log_active_frame.pack(fill="both", expand=True, padx=20, pady=5)

def refresh_quest_log_screen(app):
    # Update Scrip
    current_scrip = app.save_data.get('scrip', 0)
    if hasattr(app, 'quest_log_scrip_label'):
        app.quest_log_scrip_label.config(text=f"Scrip: {current_scrip}")

    # --- Refresh Quests (Main + Side) ---
    for w in app.quest_log_quests_frame.winfo_children(): w.destroy()
    
    mq_idx = app.save_data.get("current_main_quest_index", 0)
    if mq_idx < len(app.main_quests):
        _create_full_quest_widget(app, app.quest_log_quests_frame, app.main_quests[mq_idx], "MAIN")
        
    active_side_ids = app.save_data.get("active_side_quests", [])
    static_db = app.side_quests
    dynamic_db = app.save_data.get("generated_side_quests", [])
    
    for q_id in active_side_ids:
        q_data = next((q for q in static_db if q["id"] == q_id), None)
        if not q_data:
            q_data = next((q for q in dynamic_db if q["id"] == q_id), None)
        if q_data:
            _create_full_quest_widget(app, app.quest_log_quests_frame, q_data, "SIDE")

    # --- Refresh Tasks ---
    for w in app.quest_log_active_frame.winfo_children(): w.destroy()
    active_tasks = [t for t in app.save_data.get("tasks", []) if t.get("state") == "pending"]
    active_tasks.sort(key=lambda x: not x.get("is_emergency", False))
    
    if not active_tasks:
        tk.Label(app.quest_log_active_frame, text="No active contracts.", fg="#555555", bg="#111111", font=("Courier", 12)).pack(anchor="w")
    else:
        for task in active_tasks:
            _create_log_task_widget(app, app.quest_log_active_frame, task)

def _create_full_quest_widget(app, parent, quest, q_type):
    bg = "#222222"
    border_col = "#FFD700" if q_type == "MAIN" else "#00BFFF"
    
    f = tk.Frame(parent, bg=bg, bd=2, relief="solid", highlightbackground=border_col, highlightthickness=1)
    f.pack(fill="x", pady=5)
    
    tk.Label(f, text=f"{q_type}: {quest['title']}", fg=border_col, bg=bg, font=("Courier", 11, "bold")).pack(anchor="w", padx=5, pady=2)
    
    if "flavor_text" in quest:
        tk.Label(f, text=quest["flavor_text"], fg="#AAAAAA", bg=bg, font=("Courier", 9), wraplength=app.current_wrap_width-60, justify="left").pack(anchor="w", padx=10, pady=2)
        
    all_complete = True
    objectives_list = quest.get("objectives", [])
    raw_objs = quest.get("raw_objectives")
    
    q_id = quest.get("id", "main")
    
    for i, obj in enumerate(objectives_list):
        is_done = _is_quest_objective_done(app, q_id, i)
        
        display_text = obj
        if raw_objs and i < len(raw_objs):
            # Format: [icon, text, color, current_count, target_count]
            current_count = raw_objs[i][3]
            target_count = raw_objs[i][4]
            if target_count > 1 and not is_done:
                display_text = f"{obj} [{target_count - current_count}/{target_count}]"
            elif target_count > 1 and is_done:
                 display_text = f"{obj} [Complete]"
        
        if not is_done: all_complete = False
            
        fg = "#FFFFE0" if not is_done else "#555555"
        font_style = ("Courier", 9) if not is_done else ("Courier", 9, "overstrike")
        
        row = tk.Frame(f, bg=bg)
        row.pack(fill="x", padx=10)
        row.columnconfigure(1, weight=1)
        tk.Label(row, text="➤", fg=fg, bg=bg, font=font_style, width=3, anchor="center").grid(row=0, column=0, sticky="n")
        tk.Label(row, text=display_text, fg=fg, bg=bg, font=font_style, wraplength=app.current_wrap_width-80, justify="left").grid(row=0, column=1, sticky="w")

    if all_complete:
        btn_frame = tk.Frame(f, bg=bg)
        btn_frame.pack(fill="x", pady=5, padx=10)
        
        if q_type == "MAIN":
            tk.Button(btn_frame, text="COMPLETE QUEST", command=lambda: _complete_main_quest(app, quest, f), bg="#004400", fg="#00FF00", font=("Courier", 10, "bold")).pack(fill="x")
        
        elif q_type == "SIDE":
            r_type = quest.get("reward", {}).get("type")
            unlocks = quest.get("reward", {}).get("unlocks_feature")
            requires_source_completion = r_type in ["recruit_companion", "loyalty_complete"] or unlocks in ["shop", "bar", "hideout", "insurance"]
            
            if requires_source_completion: 
                source_map = {"shop": "Shop", "bar": "Bar", "hideout": "Shelter", "insurance": "Shopkeeper"}
                source_name = "Companion" if r_type in ["recruit_companion", "loyalty_complete"] else source_map.get(unlocks, "Source Location")
                tk.Label(btn_frame, text=f"Return to {source_name} to Finalize", fg="#FFFF00", bg=bg, font=("Courier", 10, "bold")).pack(fill="x")
            else:
                tk.Button(btn_frame, text="COMPLETE MISSION", command=lambda: _complete_side_quest_generic(app, quest, f), bg="#004400", fg="#00FF00", font=("Courier", 10, "bold")).pack(fill="x")

def _complete_main_quest(app, quest, widget_frame):
    for w in widget_frame.winfo_children(): w.destroy()
    bg = "#222222"
    tk.Label(widget_frame, text="QUEST COMPLETE", fg="#00FF00", bg=bg, font=("Courier", 12, "bold")).pack(pady=10)
    next_idx = app.save_data.get("current_main_quest_index", 0) + 1
    app.save_data["current_main_quest_index"] = next_idx
    engine.save_save_data(app.save_data)
    tk.Button(widget_frame, text="CONTINUE", command=lambda: refresh_quest_log_screen(app), bg="#003300", fg="#00FF00", font=("Courier", 10)).pack(pady=10)

def _complete_side_quest_generic(app, quest, widget_frame):
    for w in widget_frame.winfo_children(): w.destroy()
    bg = "#222222"
    unlocks = quest.get("reward", {}).get("unlocks_feature")
    if unlocks == "shop": app.save_data["shop_unlocked"] = True
    if unlocks == "bar": app.save_data["bar_unlocked"] = True
    if unlocks == "hideout": app.save_data["hideout_unlocked"] = True
    if unlocks == "insurance": app.save_data["insurance_unlocked"] = True 
    
    if quest["id"] in app.save_data.get("active_side_quests", []):
        app.save_data["active_side_quests"].remove(quest["id"])
    engine.save_save_data(app.save_data)
    
    tk.Label(widget_frame, text="MISSION COMPLETE", fg="#00FF00", bg=bg, font=("Courier", 12, "bold")).pack(pady=10)
    tk.Button(widget_frame, text="CONTINUE", command=lambda: refresh_quest_log_screen(app), bg="#003300", fg="#00FF00", font=("Courier", 10)).pack(pady=10)

# ----------------------------------------------------------------------
# QUEST LOG WIDGET (CONTRACT)
# ----------------------------------------------------------------------
def _create_log_task_widget(app, parent, task):
    is_emergency = task.get("is_emergency", False)
    bg = "#330000" if is_emergency else "#222222"
    diff = task.get("difficulty", "easy")
    bd_col = "#444444"
    title_col = "#FFFFFF"
    if diff == "medium": bd_col = "#888800"; title_col = "#FFFF00"
    elif diff == "hard": bd_col = "#880000"; title_col = "#FF4444"
    if is_emergency: bd_col = "#FF0000"; title_col = "#FF4444"
    
    f = tk.Frame(parent, bg=bg, bd=2, relief="solid", highlightbackground=bd_col, highlightthickness=1)
    f.pack(fill="x", pady=4, padx=5)
    
    h = tk.Frame(f, bg=bg)
    h.pack(fill="x", pady=2)
    
    title_text = task['name']
    if is_emergency: title_text = f"🚨 {title_text}"
    cycles = task.get("cycles_remaining", 0)
    cycle_text = f"[{cycles} Days]" if cycles > 0 else "[Last Day]"
    
    lbl = tk.Label(h, text=f"{title_text} {cycle_text}", fg=title_col, bg=bg, font=("Courier", 11, "bold"))
    lbl.pack(side="left", padx=5)
    
    # TOOLTIP LOGIC
    tags = task.get("tags", [])
    if tags:
        c_id, _ = companions.get_active_companion(app.save_data)
        c_tags = []
        if c_id:
            roster = companions.load_companion_roster()
            c_tags = roster.get(c_id, {}).get("task_tags", [])
            
        tooltip_content = [("Tags: ", "#AAAAAA")]
        for i, tag in enumerate(tags):
            col = "#00FF00" if tag in c_tags else "#FFFFFF"
            sep = ", " if i < len(tags) - 1 else ""
            tooltip_content.append((tag + sep, col))
            
        # REPLACED LOCAL USAGE with horizontal=True for tags
        etw_ui_styles.create_tooltip(lbl, tooltip_content, horizontal=True)
    
    for icon, txt, col, cur, tgt in task.get("objectives", []):
        row = tk.Frame(f, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        row.columnconfigure(1, weight=1)
        
        is_struck = (cur <= 0)
        display_txt = txt
        if not is_struck and tgt > 1:
            display_txt = f"{txt} [{tgt - cur}/{tgt} Left]"
        elif is_struck:
            display_txt = f"{txt} (Done)"
        
        final_col = _get_objective_color(txt, col, is_struck)
        font_style = ("Courier", 10, "overstrike") if is_struck else ("Courier", 10)
        
        tk.Label(row, text=icon, fg=final_col, bg=bg, font=font_style, width=3, anchor="center").grid(row=0, column=0, sticky="n")
        tk.Label(row, text=display_txt, fg=final_col, bg=bg, font=font_style, wraplength=app.current_wrap_width-80, justify="left").grid(row=0, column=1, sticky="w")

# ----------------------------------------------------------------------
# RAID MAIN QUEST DISPLAY (Helpers for etw_ui_game)
# ----------------------------------------------------------------------

def refresh_main_quest_display(app, frame, is_log_view):
    """
    Shared renderer used by the Raid HUD.
    """
    pass 

def refresh_taskboard_ui(app, parent_frame):
    for w in parent_frame.winfo_children(): w.destroy()
    pool = app.save_data.get("taskboard_pool", [])
    if not pool:
        tasks.refresh_taskboard(app.save_data)  
        pool = app.save_data.get("taskboard_pool", [])
    pool.sort(key=lambda x: not x.get("is_emergency", False))
    for task in pool:
        _create_taskboard_widget(app, parent_frame, task)

def _create_taskboard_widget(app, parent, task):
    is_emergency = task.get("is_emergency", False)
    bg = "#330000" if is_emergency else "#222222"
    diff = task.get("difficulty", "easy")
    bd_col = "#444444"
    diff_color = "#00FF00"
    if diff == "medium": bd_col = "#888800"; diff_color = "#FFFF00"
    elif diff == "hard": bd_col = "#880000"; diff_color = "#FF4444"
    if is_emergency: bd_col = "#FF0000"; diff_color = "#FF4444"
    
    f = tk.Frame(parent, bg=bg, bd=2, relief="solid", highlightbackground=bd_col, highlightthickness=1)
    f.pack(fill="x", padx=5, pady=4)
    h = tk.Frame(f, bg=bg)
    h.pack(fill="x")
    
    title_text = task['name']
    if is_emergency: title_text = f"🚨 {title_text}"
    cycles = task.get("cycles_remaining", 0)
    cycle_text = f"[{cycles} Days]" if cycles > 0 else "[Last Day]"
    
    lbl = tk.Label(h, text=f"{title_text} {cycle_text}", fg=diff_color, bg=bg, font=("Courier", 11, "bold"))
    lbl.pack(side="left", padx=5)
    
    # TOOLTIP LOGIC
    tags = task.get("tags", [])
    if tags:
        c_id, _ = companions.get_active_companion(app.save_data)
        c_tags = []
        if c_id:
            roster = companions.load_companion_roster()
            c_tags = roster.get(c_id, {}).get("task_tags", [])
            
        tooltip_content = [("Tags: ", "#AAAAAA")]
        for i, tag in enumerate(tags):
            col = "#00FF00" if tag in c_tags else "#FFFFFF"
            sep = ", " if i < len(tags) - 1 else ""
            tooltip_content.append((tag + sep, col))
            
        # REPLACED LOCAL USAGE with horizontal=True for tags
        etw_ui_styles.create_tooltip(lbl, tooltip_content, horizontal=True)
    
    btn_frame = tk.Frame(h, bg=bg)
    btn_frame.pack(side="right", padx=5, pady=2)
    
    if not is_emergency:
        rerolls = app.save_data.get("inventory", {}).get("task_reroll", 0)
        if rerolls > 0:
            tk.Button(btn_frame, text=f"REROLL ({rerolls})", command=lambda t=task["task_number"]: _reroll_task(app, t), bg="#444400", fg="#FFFF00", font=("Courier", 8)).pack(side="left", padx=5)
            
    tk.Button(btn_frame, text="ACCEPT", command=lambda t=task["task_number"]: _accept_task(app, t), bg="#004400", fg="#00FF00", font=("Courier", 9)).pack(side="left")
    
    for icon, txt, col, cur, tgt in task.get("objectives", []):
        row = tk.Frame(f, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        row.columnconfigure(1, weight=1)
        
        display_txt = txt
        if tgt > 1: display_txt = f"{txt} [{tgt}]"
        
        final_col = _get_objective_color(txt, col, False)
        tk.Label(row, text=icon, fg=final_col, bg=bg, font=("Courier", 10), width=3, anchor="center").grid(row=0, column=0, sticky="n")
        tk.Label(row, text=display_txt, fg=final_col, bg=bg, font=("Courier", 10), wraplength=350, justify="left").grid(row=0, column=1, sticky="w")

def _accept_task(app, task_num):
    res = tasks.accept_task_from_board(task_num, app.save_data) 
    if res["success"]:
        refresh_taskboard_ui(app, app.town_taskboard_frame)
        # LOCAL IMPORT to prevent circular dependency
        from etw_ui_town import update_town_stats 
        update_town_stats(app)
    else:
        app.show_temporary_text(app.taskboard_error_label, res["message"], "#FF0000")

def _reroll_task(app, task_num):
    if tasks.reroll_task_on_board(task_num, app.save_data):
        refresh_taskboard_ui(app, app.town_taskboard_frame)
    else:
        app.show_temporary_text(app.taskboard_error_label, "Reroll Failed", "#FF0000")

# ----------------------------------------------------------------------
# NEW TICK HANDLER
# ----------------------------------------------------------------------
def _tick_task_objective(app, task, obj_idx):
    task_logic.tick_dynamic_task_objective(app, task, obj_idx, is_quest=False)

def _tick_quest_objective(app, quest, obj_idx):
    task_logic.tick_dynamic_task_objective(app, quest, obj_idx, is_quest=True)