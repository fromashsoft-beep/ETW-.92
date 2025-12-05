import tkinter as tk
import math

# Foundation
import etw_config as config
import etw_io as io

# Core & Systems
import etw_engine as engine
import etw_hideout as hideout_logic
import etw_companions as companions
import etw_tasks 
import etw_ui_town 
import etw_bridge as bridge 
import etw_inventory as inventory 
import etw_ui_styles # Shared UI Utilities

# ----------------------------------------------------------------------
# HIDEOUT UI MODULE
# ----------------------------------------------------------------------

def _is_quest_complete(app, q_id):
    if "quest_progress" not in app.save_data: return False
    prog = app.save_data["quest_progress"].get(str(q_id), [])
    return len(prog) > 0 and all(prog)

def build_hideout_screen(app, frame):
    # 1. Header (Top)
    tk.Label(frame, text="Super Duper Shelter", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=5)

    # 2. Navigation Bar (Underneath Header)
    nav_frame = tk.Frame(frame, bg="#111111")
    nav_frame.pack(fill="x", pady=5, padx=20)
    
    # Return Button (Left)
    tk.Button(nav_frame, text="Return to Town", command=app.show_town_screen, bg="#003300", fg="#00FF00", font=("Courier", 12, "bold")).pack(side="left")
    
    # Currency Display (Right)
    # Container for Scrip + Components
    curr_frame = tk.Frame(nav_frame, bg="#111111")
    curr_frame.pack(side="right")
    
    app.hideout_scrip_label = tk.Label(curr_frame, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.hideout_scrip_label.pack(anchor="e")
    
    app.hideout_comps_label = tk.Label(curr_frame, text="", fg="#00BFFF", bg="#111111", font=("Courier", 10, "bold"))
    app.hideout_comps_label.pack(anchor="e")
    
    # 3. Feedback Label
    app.hideout_feedback_label = tk.Label(frame, text="", fg="#00FF00", bg="#111111", font=("Courier", 10, "bold"))
    app.hideout_feedback_label.pack(pady=5)
    
    # 4. Management Button
    tk.Button(frame, text="Manage Crew", command=lambda: _build_companion_roster_ui(app), bg="#003333", fg="#00FFFF", font=("Courier", 12, "bold")).pack(pady=5)
    
    # 5. Main Container
    app.hideout_container = tk.Frame(frame, bg="#111111")
    app.hideout_container.pack(fill="both", expand=True, padx=10, pady=5)
    # Configure grid weights for 2 columns
    app.hideout_container.columnconfigure(0, weight=1, uniform="station_col")
    app.hideout_container.columnconfigure(1, weight=1, uniform="station_col")
    
    # NOTE: Scan trigger moved to refresh_hideout_ui to prevent startup firing

def _trigger_entry_scan(app):
    """
    Refreshes inventory data on entry to ensure upgrades have valid data to check against.
    """
    game_path = app.save_data.get("game_install_path", "")
    if game_path:
        app.hideout_feedback_label.config(text="Scanning Inventory...")
        bridge.trigger_inventory_scan(game_path)
        app.after(1500, lambda: _finalize_entry_scan(app))

def _finalize_entry_scan(app):
    inventory.perform_full_inventory_sync(app.save_data)
    if hasattr(app, 'hideout_feedback_label') and app.hideout_feedback_label.winfo_exists():
        app.hideout_feedback_label.config(text="Inventory Synced.")
        app.after(2000, lambda: app.hideout_feedback_label.config(text=""))
    # Refresh to update Dismantle lists if open
    refresh_hideout_ui(app)

def refresh_hideout_ui(app):
    # Update Scrip
    current_scrip = app.save_data.get('scrip', 0)
    if hasattr(app, 'hideout_scrip_label'):
        app.hideout_scrip_label.config(text=f"Scrip: {current_scrip}")
        
    # Update Components (NEW)
    current_comps = app.save_data.get('components', 0)
    if hasattr(app, 'hideout_comps_label'):
        app.hideout_comps_label.config(text=f"Components: {current_comps}")
        
    app.hideout_feedback_label.config(text="")
    
    # If we are NOT in a specific submenu (checked by children count or tag?), rebuild stations.
    # The current architecture rebuilds the whole container.
    # We need to detect if we are in "Crafting Mode" to persist that view?
    # Simple approach: Default to Stations Grid.
    # But if the user is in Crafting Screen, 'refresh' might kick them out.
    # However, 'collect' and 'cancel' actions call refresh_hideout_ui.
    # We should probably pass a 'context' or just let it reset to main menu for safety,
    # unless we store 'current_view' state.
    # Given the complexity, resetting to Main Station Grid is safer/cleaner for now.
    
    _build_stations_ui(app)
    
    if app.save_data.get("hideout_unlocked", False):
        # Only trigger scan if this was a "Full Refresh" (Entry), not a partial UI update?
        # We rely on manual/entry triggers mostly.
        pass

def _build_stations_ui(app):
    for w in app.hideout_container.winfo_children(): w.destroy()
    
    if not app.save_data.get("hideout_unlocked", False):
        _build_locked_hideout_ui(app)
        return

    # FIX: Use IO/Config
    content = io.load_json(config.PATHS["content_hideout"])
    stations_conf = content.get("stations", [])
    user_stations = app.save_data.get("hideout_stations", {})
    generated_costs = app.save_data.get("generated_station_costs", {})
    
    # Grid Layout: Row-major order (Left, Right, Next Row)
    for i, s_conf in enumerate(stations_conf):
        row = i // 2
        col = i % 2
        
        # Container frame for the station card
        card_frame = tk.Frame(app.hideout_container, bg="#111111")
        card_frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        
        s_id = s_conf["id"]
        s_data = user_stations.get(s_id, {})
        s_costs = generated_costs.get(s_id, {})
        
        _build_station_card(app, card_frame, s_conf, s_data, s_costs)

# ----------------------------------------------------------------------
# COMPANION ROSTER UI
# ----------------------------------------------------------------------
def _build_companion_roster_ui(app):
    for w in app.hideout_container.winfo_children(): w.destroy()
    
    # Span header across columns
    header_frame = tk.Frame(app.hideout_container, bg="#111111")
    header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
    
    tk.Label(header_frame, text="Crew Roster", fg="#00FFFF", bg="#111111", font=("Courier", 16, "bold")).pack(side="left")
    tk.Button(header_frame, text="Back to Stations", command=lambda: refresh_hideout_ui(app), bg="#333333", fg="#FFFFFF").pack(side="right")
    
    comps = app.save_data.get("companions", {})
    recruited_ids = [cid for cid, cdata in comps.items() if cdata.get("unlocked")]
    
    if not recruited_ids:
        tk.Label(app.hideout_container, text="No companions recruited yet.\nCheck the Lounge in town.", fg="#555555", bg="#111111", font=("Courier", 12)).grid(row=1, column=0, columnspan=2, pady=20)
        return

    # Use a sub-grid for cards so we don't mess up the main container config
    roster_grid = tk.Frame(app.hideout_container, bg="#111111")
    roster_grid.grid(row=1, column=0, columnspan=2, sticky="nsew")
    roster_grid.columnconfigure(0, weight=1, uniform="roster_group")
    roster_grid.columnconfigure(1, weight=1, uniform="roster_group")
    
    for i, c_id in enumerate(recruited_ids):
        c_data = comps.get(c_id)
        roster = companions.load_companion_roster()
        c_def = roster.get(c_id)
        
        if not c_def: continue
        
        row_idx = i // 2
        col_idx = i % 2
        is_active = (c_id == app.save_data.get("global_companion_state", {}).get("active_companion_id"))
        
        _render_companion_card(app, roster_grid, row_idx, col_idx, c_id, c_def, c_data, is_active)

def _render_companion_card(app, parent, row, col, c_id, c_def, c_data, is_active):
    bg_color = "#002200" if is_active else "#222222"
    border_color = "#00FF00" if is_active else "#444444"
    
    f = tk.Frame(parent, bg=bg_color, bd=2, relief="solid", highlightbackground=border_color, highlightthickness=1)
    f.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
    
    h = tk.Frame(f, bg=bg_color)
    h.pack(fill="x", padx=5, pady=5)
    
    name_txt = f"{c_def['name']} ({c_def['archetype']})"
    if is_active: name_txt += " [ACTIVE]"
    tk.Label(h, text=name_txt, fg="#FFFFFF", bg=bg_color, font=("Courier", 11, "bold")).pack(side="left")
    
    lvl = c_data.get("level", 1)
    tk.Label(h, text=f"Lvl {lvl}", fg="#FFD700", bg=bg_color, font=("Courier", 11, "bold")).pack(side="right")
    
    body = tk.Frame(f, bg=bg_color)
    body.pack(fill="x", padx=5, pady=2)
    
    flavor = c_def["flavor_loyal"] if c_data.get("loyalty_completed") else c_def["personality"]
    wrap_width = int(app.current_wrap_width / 2) - 30 
    tk.Label(body, text=f"\"{flavor}\"", fg="#AAAAAA", bg=bg_color, font=("Courier", 9, "italic"), wraplength=wrap_width, justify="left").pack(anchor="w", pady=(0, 5))
    
    buff_name = c_def["base_buff_type"].replace("_", " ").title()
    tk.Label(body, text=f"Buff: {buff_name}", fg="#00FFFF", bg=bg_color, font=("Courier", 10)).pack(anchor="w")
    
    xp = c_data.get("xp", 0)
    next_xp = companions.LEVEL_XP_THRESHOLDS.get(lvl + 1, 99999)
    curr_base = companions.LEVEL_XP_THRESHOLDS.get(lvl, 0)
    
    if lvl >= 5:
        tk.Label(body, text="MAX LEVEL", fg="#FFD700", bg=bg_color, font=("Courier", 9)).pack(anchor="w")
    else:
        req = next_xp - curr_base
        progress = xp - curr_base
        pct = min(1.0, progress / req) if req > 0 else 0
        tk.Label(body, text=f"XP: {progress}/{req}", fg="#888888", bg=bg_color, font=("Courier", 9)).pack(anchor="w")
        canvas = tk.Canvas(body, height=4, bg="#000000", highlightthickness=0)
        canvas.pack(fill="x", pady=2)
        canvas.after(50, lambda: _draw_xp_bar(canvas, pct))
        
    btn_row = tk.Frame(f, bg=bg_color)
    btn_row.pack(fill="x", padx=5, pady=5)
    
    # --- QUEST LOGIC & BUTTON ---
    q_id_loyalty = f"loyalty_{c_id}"
    is_quest_active = q_id_loyalty in app.save_data.get("active_side_quests", [])
    
    btn_text = "Talk"
    btn_bg = "#333333"
    btn_fg = "#FFFFFF"
    
    # Determine Status
    has_quest_available = (lvl >= 5 and c_data.get("loyalty_unlocked") and not c_data.get("loyalty_completed") and not is_quest_active)
    is_quest_turnin = (is_quest_active and _is_quest_complete(app, q_id_loyalty))
    
    if has_quest_available or is_quest_turnin:
        btn_bg = "#004400"
        btn_fg = "#00FF00"
        
    tk.Button(btn_row, text=btn_text, command=lambda: _open_inline_companion_talk(app, c_id, c_def, c_data), 
              bg=btn_bg, fg=btn_fg, font=("Courier", 9, "bold")).pack(side="left")

    if is_active:
        tk.Label(btn_row, text="Currently Active", fg="#00FF00", bg=bg_color, font=("Courier", 10, "bold")).pack(side="right")
    else:
        tk.Button(btn_row, text="Set Active", command=lambda: _set_active_companion(app, c_id), bg="#333333", fg="#FFFFFF").pack(side="right")

def _draw_xp_bar(c, p):
     c.delete("all")
     w = c.winfo_width() if c.winfo_width() > 1 else 300 
     c.create_rectangle(0, 0, int(w * p), 4, fill="#00FF00", width=0)

def _set_active_companion(app, c_id):
    if companions.set_active_companion(app.save_data, c_id):
        app.show_temporary_text(app.hideout_feedback_label, "Companion Swapped!", "#00FF00")
        _build_companion_roster_ui(app)
        etw_ui_town.update_town_stats(app) 
    else:
        app.show_temporary_text(app.hideout_feedback_label, "Error swapping.", "#FF0000")

# ----------------------------------------------------------------------
# INLINE COMPANION DIALOG
# ----------------------------------------------------------------------
def _open_inline_companion_talk(app, c_id, c_def, c_data):
    """
    Replaces the Hideout content with a dialog screen.
    """
    for w in app.hideout_container.winfo_children(): w.destroy()
    
    # Dialog Frame (Grid spanning all)
    d_frame = tk.Frame(app.hideout_container, bg="#111111")
    d_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=20, pady=20)
    
    tk.Label(d_frame, text=f"Conversing with {c_def['name']}", fg="#00FF00", bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(d_frame, text=f"({c_def['descriptor']})", fg="#AAAAAA", bg="#111111", font=("Courier", 10)).pack()
    
    # Determine Text
    flavor = c_def["personality"]
    if c_data.get("loyalty_completed"): flavor = c_def["flavor_loyal"]
    elif c_data.get("level", 1) < 5: flavor = c_def["flavor_recruit"] # Fallback flavor
    
    tk.Label(d_frame, text=f"\"{flavor}\"", fg="#FFFFFF", bg="#111111", font=("Courier", 12, "italic"), wraplength=500, justify="center").pack(pady=30)
    
    # Actions
    act_row = tk.Frame(d_frame, bg="#111111")
    act_row.pack(pady=20)
    
    # Check Quest Logic
    q_id_loyalty = f"loyalty_{c_id}"
    is_quest_active = q_id_loyalty in app.save_data.get("active_side_quests", [])
    has_quest_available = (c_data.get("level", 1) >= 5 and c_data.get("loyalty_unlocked") and not c_data.get("loyalty_completed") and not is_quest_active)
    
    if has_quest_available:
        tk.Button(act_row, text=f"Discuss: {c_def['quest_loyalty']['title']}", 
                  command=lambda: _trigger_loyalty_quest(app, c_id), 
                  bg="#004400", fg="#FFFF00", font=("Courier", 11, "bold")).pack(side="left", padx=10)
                  
    elif is_quest_active:
        if _is_quest_complete(app, q_id_loyalty):
            tk.Button(act_row, text="Complete Loyalty Mission", 
                      command=lambda: _complete_loyalty_quest(app, c_id), 
                      bg="#004400", fg="#00FF00", font=("Courier", 11, "bold")).pack(side="left", padx=10)
        else:
            tk.Label(act_row, text="[Loyalty Mission In Progress]", fg="#FFFF00", bg="#111111", font=("Courier", 10)).pack(side="left", padx=10)
    
    tk.Button(act_row, text="Leave", command=lambda: _build_companion_roster_ui(app), bg="#333333", fg="#FFFFFF", font=("Courier", 11)).pack(side="left", padx=10)

def _trigger_loyalty_quest(app, c_id):
    import etw_tasks
    quest = etw_tasks.generate_companion_quest(app.save_data, c_id, "loyalty")
    if quest:
        app.show_temporary_text(app.hideout_feedback_label, "Loyalty Quest Started!", "#FF00FF")
        _build_companion_roster_ui(app)
    else:
        app.show_temporary_text(app.hideout_feedback_label, "Error.", "#FF0000")

def _complete_loyalty_quest(app, c_id):
    companions.complete_loyalty(app.save_data, c_id)
    q_id_loyalty = f"loyalty_{c_id}"
    if q_id_loyalty in app.save_data.get("active_side_quests", []):
        app.save_data["active_side_quests"].remove(q_id_loyalty)
    io.save_json(config.PATHS["save_data"], app.save_data)
    
    roster = companions.load_companion_roster()
    c_def = roster.get(c_id)
    app.show_temporary_text(app.hideout_feedback_label, f"{c_def['name']} is now fully loyal!", "#FF00FF")
    _build_companion_roster_ui(app)

# ----------------------------------------------------------------------
# LOCKED STATE
# ----------------------------------------------------------------------
def _build_locked_hideout_ui(app):
    q_id = "hideout_unlock"
    q_data = next((q for q in app.side_quests if q["id"] == q_id), None)
    
    center = tk.Frame(app.hideout_container, bg="#111111")
    # Grid center across both columns
    center.grid(row=0, column=0, columnspan=2)
    
    if not q_data:
        tk.Label(center, text="[SAFEHOUSE LOCKED]", fg="#FF0000", bg="#111111").pack()
        return

    active_side = app.save_data.get("active_side_quests", [])
    is_active = q_id in active_side
    
    status_text = "[QUEST IN PROGRESS]" if is_active else "[SAFEHOUSE LOCKED]"
    status_col = "#FFFF00" if is_active else "#FF0000"
    
    tk.Label(center, text=status_text, fg=status_col, bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(center, text=q_data["title"], fg="#FFFFFF", bg="#111111", font=("Courier", 14, "bold")).pack(pady=5)
    tk.Label(center, text=q_data.get("flavor_text", ""), fg="#AAAAAA", bg="#111111", font=("Courier", 12), wraplength=600, justify="center").pack(pady=10)
    
    tk.Label(center, text="Requirements:", fg="#00FFFF", bg="#111111", font=("Courier", 12, "bold")).pack(pady=(10,5))
    for obj in q_data.get("objectives", []):
        tk.Label(center, text=f"- {obj}", fg="#FFFFFF", bg="#111111", font=("Courier", 11)).pack()

    if is_active:
        tk.Label(center, text="(Check Quest Log to track progress)", fg="#555555", bg="#111111", font=("Courier", 10)).pack(pady=20)
        progress = app.save_data.get("quest_progress", {}).get(q_id, [])
        all_done = (len(progress) > 0 and all(progress))
        state = "normal" if all_done else "disabled"
        bg_col = "#004400" if all_done else "#222222"
        txt = "COMPLETE QUEST" if all_done else "Objectives Pending..."
        tk.Button(center, text=txt, state=state, bg=bg_col, fg="#00FF00", command=lambda: _complete_hideout_quest(app, center, q_data), font=("Courier", 12, "bold")).pack(pady=20)
    else:
        tk.Button(center, text="ACCEPT QUEST", command=lambda: _accept_side_quest(app, q_id), bg="#003300", fg="#00FF00", font=("Courier", 14, "bold")).pack(pady=20)

def _accept_side_quest(app, q_id):
    if "active_side_quests" not in app.save_data: app.save_data["active_side_quests"] = []
    if q_id not in app.save_data["active_side_quests"]:
        app.save_data["active_side_quests"].append(q_id)
        q_data = next((q for q in app.side_quests if q["id"] == q_id), None)
        count = len(q_data.get("objectives", [])) if q_data else 1
        if "quest_progress" not in app.save_data: app.save_data["quest_progress"] = {}
        app.save_data["quest_progress"][q_id] = [False] * count
        io.save_json(config.PATHS["save_data"], app.save_data)
        refresh_hideout_ui(app)

def _complete_hideout_quest(app, parent_frame, q_data):
    for w in parent_frame.winfo_children(): w.destroy()
    tk.Label(parent_frame, text="ACCESS GRANTED", fg="#00FF00", bg="#111111", font=("Courier", 18, "bold")).pack(pady=20)
    tk.Label(parent_frame, text=q_data.get("completion_text", "Done!"), fg="#FFFFFF", bg="#111111", font=("Courier", 12), wraplength=600, justify="center").pack(pady=10)
    if q_data["id"] in app.save_data.get("active_side_quests", []):
        app.save_data["active_side_quests"].remove(q_data["id"])
    app.save_data["hideout_unlocked"] = True
    if "hideout_stations" not in app.save_data: app.save_data["hideout_stations"] = {}
    if not app.save_data.get("generated_station_costs"): hideout_logic.generate_station_costs(app.save_data)
    io.save_json(config.PATHS["save_data"], app.save_data)
    tk.Button(parent_frame, text="ENTER SHELTER", command=lambda: refresh_hideout_ui(app), bg="#003300", fg="#00FF00", font=("Courier", 14, "bold")).pack(pady=20)

# ----------------------------------------------------------------------
# STATION CARDS
# ----------------------------------------------------------------------
def _build_station_card(app, parent, conf, user_data, cost_data):
    # Using 'pack' inside the grid cell
    f = tk.Frame(parent, bg="#222222", bd=2, relief="ridge")
    f.pack(fill="both", expand=True) # Fill the grid cell
    
    s_id = conf["id"]
    level = user_data.get("level", 0)
    s_type = conf.get("type", "passive_production")
    
    h_frame = tk.Frame(f, bg="#222222")
    h_frame.pack(fill="x", padx=5, pady=2)
    name_color = "#00FFFF" if level > 0 else "#888888"
    lvl_text = f"Lvl {level}" if level > 0 else "Locked"
    tk.Label(h_frame, text=conf["name"], fg=name_color, bg="#222222", font=("Courier", 12, "bold")).pack(side="left")
    tk.Label(h_frame, text=lvl_text, fg="#AAAAAA", bg="#222222", font=("Courier", 10)).pack(side="right")
    
    etw_ui_styles.create_tooltip(h_frame, conf["description"])
    
    if level == 0:
        _build_upgrade_ui(app, f, s_id, 1, cost_data)
        return

    lvl_conf = next((l for l in conf["levels"] if l["level"] == level), None)
    
    if s_type == "passive_production":
        storage = user_data.get("storage", 0)
        progress = user_data.get("progress", 0.0)
        cap = math.ceil(level / 2.0)
        rate = lvl_conf.get("production_rate", 60)
        progress_pct = min(1.0, progress / rate) if rate > 0 else 0
        if storage >= cap: progress_pct = 1.0 
        rem_min = int(max(0, rate - progress))
        prog_txt = f"{int(progress_pct*100)}% ({rem_min}m)"
        if storage >= cap: prog_txt = "Full"
        _render_progress_bar(app, f, progress_pct, prog_txt, "#00AA00")
        if storage > 0:
            tk.Button(f, text="COLLECT", command=lambda: _collect_station(app, s_id), bg="#004400", fg="#00FF00", font=("Courier", 10, "bold")).pack(pady=2)

    elif s_type == "active_crafting":
        btn_txt = "Workbench" if "workbench" in s_id else "Craft"
        tk.Button(f, text=btn_txt, command=lambda: _render_crafting_screen(app, s_id, level), bg="#440044", fg="#FF00FF", font=("Courier", 10, "bold")).pack(pady=2)
        
        active_slots = user_data.get("active_slots", [])
        storage = user_data.get("storage", 0) 
        if storage > 0:
             tk.Button(f, text=f"COLLECT ({storage})", command=lambda: _collect_active_craft(app, s_id), bg="#004400", fg="#00FF00", font=("Courier", 10, "bold")).pack(pady=2)
        max_slots = lvl_conf.get("slots", 1)
        display_slots = active_slots[:]
        while len(display_slots) < max_slots: display_slots.append({})
        for i, slot in enumerate(display_slots):
            row = tk.Frame(f, bg="#222222")
            row.pack(fill="x", padx=5, pady=1)
            
            if slot and slot.get("code"):
                rate = lvl_conf.get("production_rate", 60)
                progress = slot.get("progress", 0.0)
                pct = min(1.0, progress / rate) if rate > 0 else 0
                rem_min = int(max(0, rate - progress))
                prog_txt = f"{int(pct*100)}% ({rem_min}m)"
                cap = math.ceil(level / 2.0)
                if user_data.get("storage", 0) >= cap: prog_txt = "Storage Full"
                
                # Check job type for visual distinction
                bar_col = "#AAAA00" # Default item
                if slot.get("result_type") == "currency": 
                    bar_col = "#0088AA" # Blue for dismantling
                    
                _render_progress_bar(app, row, pct, prog_txt, bar_col)
            else:
                tk.Label(row, text=f"Slot {i+1}: Idle", fg="#555555", bg="#222222", font=("Courier", 8)).pack(anchor="w")

    elif s_type == "passive_buff":
        buff = lvl_conf.get("buff", {})
        b_val = buff.get("value", 0)
        b_type = buff.get("type", "unknown")
        txt = f"Active: {b_type} +{b_val}"
        if "mult" in b_type: txt = f"Active: {b_type.split('_')[0].upper()} +{int(b_val*100)}%"
        if s_id == "tree_of_fortune": txt = "Effect: Increases fortune"
        tk.Label(f, text=txt, fg="#FFD700", bg="#222222", font=("Courier", 10)).pack(pady=2)

    footer = tk.Frame(f, bg="#222222")
    footer.pack(fill="x", padx=5, pady=2)
    cap = math.ceil(level / 2.0)
    current_storage = user_data.get("storage", 0)
    if s_type != "passive_buff":
        tk.Label(footer, text=f"Storage: {current_storage}/{cap}", fg="#AAAAAA", bg="#222222", font=("Courier", 8)).pack(side="left")
    next_lvl = level + 1
    if next_lvl <= 5:
        _build_upgrade_ui(app, footer, s_id, next_lvl, cost_data)
    else:
        tk.Label(footer, text="[MAX LEVEL]", fg="#555555", bg="#222222", font=("Courier", 8)).pack(side="right")

def _render_progress_bar(app, parent, pct, label_text, color):
    canvas = tk.Canvas(parent, height=14, bg="#000000", highlightthickness=0)
    canvas.pack(fill="x")
    def _draw_bar(event):
        w = event.width
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w * pct, 14, fill=color, width=0)
        canvas.create_text(w/2, 7, text=label_text, fill="#FFFFFF", font=("Courier", 8))
    canvas.bind("<Configure>", _draw_bar)

def _build_upgrade_ui(app, parent, s_id, target_level, cost_data):
    can_build, reason = hideout_logic.check_station_requirements(s_id, target_level, app.save_data)
    if not can_build:
        tk.Label(parent, text=f"LOCKED: {reason}", fg="#FF4444", bg="#222222", font=("Courier", 8)).pack(side="right")
        return
    lvl_cost = cost_data.get(str(target_level), {})
    req_items = lvl_cost.get("cost_items", [])
    # FIX: Use IO/Config
    content = io.load_json(config.PATHS["content_hideout"])
    s_conf = next((s for s in content["stations"] if s["id"] == s_id), None)
    lvl_conf = next((l for l in s_conf["levels"] if l["level"] == target_level), {})
    scrip_cost = lvl_conf.get("cost_scrip", 0)
    btn_text = "Construct" if target_level == 1 else "Upgrade"
    
    # NEW: Check inventory for missing items to highlight requirement text in red
    game_path = app.save_data.get("game_install_path", "")
    char_data = inventory.get_character_data(game_path)
    current_inv = char_data.get("inventory", [])
    
    # Tooltip construction using List of (Text, Color) tuples
    tip_content = []
    tip_content.append(("Requires:", "#FFFFFF"))
    
    # Check Scrip
    if app.save_data.get("scrip", 0) < scrip_cost:
        tip_content.append((f"- {scrip_cost} Scrip (MISSING)", "#FF4444"))
    else:
        tip_content.append((f"- {scrip_cost} Scrip", "#FFFFFF"))
        
    for item in req_items:
        name = item.get("name", "Unknown Item")
        needed_qty = item['qty']
        
        found_qty = 0
        req_code = item.get("code", "")
        req_suffix = req_code[-6:] if len(req_code) >= 6 else req_code
        
        for inv_item in current_inv:
            inv_code = inv_item.get("code", "")
            inv_suffix = inv_code[-6:] if len(inv_code) >= 6 else inv_code
            if inv_code == req_code or inv_suffix == req_suffix:
                found_qty = inv_item.get("qty", 0)
                break
        
        if found_qty < needed_qty:
            tip_content.append((f"- {needed_qty}x {name} (Have {found_qty})", "#FF4444"))
        else:
            tip_content.append((f"- {needed_qty}x {name}", "#FFFFFF"))

    btn = tk.Button(parent, text=f"{btn_text}", command=lambda: _attempt_upgrade(app, s_id, target_level, scrip_cost, req_items), bg="#333300", fg="#FFFF00", font=("Courier", 9))
    btn.pack(side="right")
    
    etw_ui_styles.create_tooltip(btn, tip_content)

# ----------------------------------------------------------------------
# CRAFTING SCREEN (SPLIT VIEW)
# ----------------------------------------------------------------------
def _render_crafting_screen(app, s_id, level):
    for w in app.hideout_container.winfo_children(): w.destroy()
    
    # Header
    tk.Label(app.hideout_container, text=f"Station: {s_id.replace('_', ' ').title()}", fg="#00FFFF", bg="#111111", font=("Courier", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
    
    # Nav
    nav = tk.Frame(app.hideout_container, bg="#111111")
    nav.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
    tk.Button(nav, text="< Back to Shelter", command=lambda: refresh_hideout_ui(app), bg="#333333", fg="#FFFFFF", font=("Courier", 10)).pack(side="left")
    
    # Active Slots Readout
    user_stations = app.save_data.get("hideout_stations", {})
    s_data = user_stations.get(s_id, {})
    active_slots = s_data.get("active_slots", [])
    
    # We need max slots config
    content = io.load_json(config.PATHS["content_hideout"])
    s_conf = next((s for s in content["stations"] if s["id"] == s_id), None)
    curr_lvl_conf = next((l for l in s_conf["levels"] if l["level"] == level), None)
    max_slots = curr_lvl_conf.get("slots", 1)
    
    busy_count = len([s for s in active_slots if s and s.get("code")])
    slots_txt = f"Slots Busy: {busy_count}/{max_slots}"
    tk.Label(nav, text=slots_txt, fg="#AAAAAA", bg="#111111", font=("Courier", 10)).pack(side="right")

    # Only do split view for WORKBENCH
    # For Ammo Press/Chemistry, we might want just "Craft".
    # But prompt implies "workbench currently has the framework".
    # If s_id contains "workbench", we use the special layout.
    
    if "workbench" in s_id.lower():
        _render_workbench_split_view(app, s_id, level, busy_count, max_slots)
    else:
        # Fallback to old generic crafting list (Standard Crafting)
        _render_generic_crafting_view(app, s_id, level, active_slots, max_slots, curr_lvl_conf)

def _render_workbench_split_view(app, s_id, level, busy_count, max_slots):
    # Fetch Data
    dismantle_list, craft_list = hideout_logic.get_workbench_data(app.save_data, level)
    
    # LEFT COLUMN: DISMANTLE
    left_frame = tk.Frame(app.hideout_container, bg="#111111", bd=2, relief="ridge")
    left_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
    
    tk.Label(left_frame, text="DISMANTLE (Inventory)", fg="#FF8800", bg="#111111", font=("Courier", 12, "bold")).pack(pady=5)
    
    if not dismantle_list:
        tk.Label(left_frame, text="No salvageable items found.", fg="#555555", bg="#111111", font=("Courier", 10)).pack(pady=20)
    else:
        # Scrollable area
        cv_l = tk.Canvas(left_frame, bg="#111111", highlightthickness=0)
        sb_l = tk.Scrollbar(left_frame, orient="vertical", command=cv_l.yview)
        fr_l = tk.Frame(cv_l, bg="#111111")
        
        fr_l.bind("<Configure>", lambda e: cv_l.configure(scrollregion=cv_l.bbox("all")))
        cv_l.create_window((0, 0), window=fr_l, anchor="nw")
        cv_l.configure(yscrollcommand=sb_l.set)
        
        cv_l.pack(side="left", fill="both", expand=True)
        sb_l.pack(side="right", fill="y")
        
        for item in dismantle_list:
            row = tk.Frame(fr_l, bg="#222222", bd=1, relief="solid")
            row.pack(fill="x", pady=2, padx=5)
            
            name = item["name"]
            qty = item["owned"]
            yield_amt = item["yield"]
            code = item["code"]
            
            tk.Label(row, text=f"{name} (x{qty})", fg="#CCCCCC", bg="#222222", font=("Courier", 9)).pack(side="left", padx=5)
            
            # Action
            state = "normal" if busy_count < max_slots else "disabled"
            btn_col = "#553300" if state == "normal" else "#333333"
            
            tk.Button(row, text=f"SCRAP (+{yield_amt})", 
                      command=lambda c=code, n=name, y=yield_amt: _do_dismantle(app, s_id, level, c, n, y),
                      bg=btn_col, fg="#FF8800", font=("Courier", 8, "bold"), state=state).pack(side="right", padx=5, pady=2)

    # RIGHT COLUMN: CRAFT
    right_frame = tk.Frame(app.hideout_container, bg="#111111", bd=2, relief="ridge")
    right_frame.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
    
    tk.Label(right_frame, text="CRAFT (Blueprints)", fg="#0088FF", bg="#111111", font=("Courier", 12, "bold")).pack(pady=5)
    
    if not craft_list:
        tk.Label(right_frame, text="No blueprints available.", fg="#555555", bg="#111111", font=("Courier", 10)).pack(pady=20)
    else:
        cv_r = tk.Canvas(right_frame, bg="#111111", highlightthickness=0)
        sb_r = tk.Scrollbar(right_frame, orient="vertical", command=cv_r.yview)
        fr_r = tk.Frame(cv_r, bg="#111111")
        
        fr_r.bind("<Configure>", lambda e: cv_r.configure(scrollregion=cv_r.bbox("all")))
        cv_r.create_window((0, 0), window=fr_r, anchor="nw")
        cv_r.configure(yscrollcommand=sb_r.set)
        
        cv_r.pack(side="left", fill="both", expand=True)
        sb_r.pack(side="right", fill="y")
        
        current_comps = app.save_data.get("components", 0)
        
        for bp in craft_list:
            is_unlocked = bp["unlocked"]
            
            bg_col = "#222222" if is_unlocked else "#1a1a1a"
            row = tk.Frame(fr_r, bg=bg_col, bd=1, relief="solid")
            row.pack(fill="x", pady=2, padx=5)
            
            name = bp["name"]
            cost = bp["cost"]
            
            name_fg = "#FFFFFF" if is_unlocked else "#555555"
            tk.Label(row, text=name, fg=name_fg, bg=bg_col, font=("Courier", 10, "bold")).pack(side="left", padx=5)
            
            if not is_unlocked:
                tk.Label(row, text="[LOCKED]", fg="#555555", bg=bg_col, font=("Courier", 8)).pack(side="right", padx=10)
            else:
                can_afford = current_comps >= cost
                slots_open = busy_count < max_slots
                
                state = "normal" if (can_afford and slots_open) else "disabled"
                btn_bg = "#004400" if (can_afford and slots_open) else "#333333"
                if not can_afford: btn_bg = "#440000"
                
                tk.Button(row, text=f"MAKE ({cost})", 
                          command=lambda b=bp["raw"]: _do_craft_blueprint(app, s_id, level, b),
                          bg=btn_bg, fg="#FFFFFF", font=("Courier", 8, "bold"), state=state).pack(side="right", padx=5, pady=2)

def _render_generic_crafting_view(app, s_id, level, active_slots, max_slots, curr_lvl_conf):
    """
    Fallback for legacy stations (Ammo Press, Chem Lab).
    """
    # Simply reuse the old scroll_frame logic inside the hideout container grid
    # We span across both columns
    
    # Recipes Logic
    # FIX: Use IO/Config
    content = io.load_json(config.PATHS["content_hideout"])
    s_conf = next((s for s in content["stations"] if s["id"] == s_id), None)
    base_yield = curr_lvl_conf.get("base_yield_mult", 1.0)
    
    recipes_by_tier = {}
    for lvl in range(1, level + 1):
        l_conf = next((l for l in s_conf["levels"] if l["level"] == lvl), None)
        if l_conf and "recipes" in l_conf:
            tier_key = f"Tier {lvl}" 
            if tier_key not in recipes_by_tier: recipes_by_tier[tier_key] = []
            recipes_by_tier[tier_key].extend(l_conf["recipes"])
            
    scroll_frame = tk.Frame(app.hideout_container, bg="#111111")
    scroll_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=20, pady=10)
    
    filled = len([s for s in active_slots if s and s.get("code")])
    
    for tier, r_list in recipes_by_tier.items():
        if not r_list: continue
        tk.Label(scroll_frame, text=f"--- {tier} ---", fg="#00FF00", bg="#111111", font=("Courier", 10, "bold")).pack(anchor="w", pady=(10, 5))
        for r in r_list:
            code = r.get("code", "")
            name = r.get("name", "Unknown")
            base_qty = r.get("qty", 1)
            final_qty = int(base_qty * base_yield)
            row = tk.Frame(scroll_frame, bg="#222222", bd=1, relief="solid")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{name}", fg="#FFFFFF", bg="#222222", font=("Courier", 11, "bold")).pack(side="left", padx=10)
            tk.Label(row, text=f"Yield: {final_qty}", fg="#FFFF00", bg="#222222", font=("Courier", 10)).pack(side="left", padx=10)
            state = "normal" if filled < max_slots else "disabled"
            btn_bg = "#005500" if filled < max_slots else "#333333"
            tk.Button(row, text="CRAFT", state=state, command=lambda c=code, q=base_qty, n=name: _start_craft_stay(app, s_id, level, c, n, q), bg=btn_bg, fg="#FFFFFF", font=("Courier", 9)).pack(side="right", padx=5, pady=5)

# ----------------------------------------------------------------------
# ACTIONS
# ----------------------------------------------------------------------
def _attempt_upgrade(app, s_id, level, scrip_cost, items):
    # 1. Scrip Check
    if app.save_data.get("scrip", 0) < scrip_cost:
        app.show_temporary_text(app.hideout_feedback_label, "Not enough Scrip!", "#FF0000")
        return

    # 2. Inventory Check & Removal (Robust)
    result = inventory.verify_and_remove_items(app.save_data, items)
    
    if not result["success"]:
        missing = result.get("missing", [])
        msg = "Missing Materials:\n" + "\n".join(missing)
        app.show_temporary_text(app.hideout_feedback_label, msg, "#FF0000", duration=4000)
        return

    # 3. Transaction Success
    app.save_data["scrip"] -= scrip_cost
    
    if s_id not in app.save_data["hideout_stations"]:
        app.save_data["hideout_stations"][s_id] = {}
        
    app.save_data["hideout_stations"][s_id]["level"] = level
    app.save_data["hideout_stations"][s_id]["progress"] = 0.0
    app.save_data["hideout_stations"][s_id]["storage"] = 0
    if "active_slots" not in app.save_data["hideout_stations"][s_id]:
        app.save_data["hideout_stations"][s_id]["active_slots"] = []
    
    io.save_json(config.PATHS["save_data"], app.save_data)
    app.show_temporary_text(app.hideout_feedback_label, f"Station Upgraded to Lvl {level}!", "#00FF00")
    refresh_hideout_ui(app)

def _collect_station(app, s_id):
    import etw_hideout
    res = etw_hideout.claim_production(app.save_data, s_id)
    color = "#00FF00" if res["success"] else "#FF0000"
    app.show_temporary_text(app.hideout_feedback_label, res["msg"], color)
    refresh_hideout_ui(app)

def _start_craft_stay(app, s_id, level, code, name, qty):
    import etw_hideout
    success, msg = etw_hideout.start_crafting_job(app.save_data, s_id, code, name, qty)
    col = "#00FF00" if success else "#FF0000"
    app.show_temporary_text(app.hideout_feedback_label, msg, col)
    # Refresh logic handles rerendering correct view (Generic vs Workbench)
    # But specifically calling render directly keeps context
    _render_crafting_screen(app, s_id, level)

def _do_dismantle(app, s_id, level, code, name, yield_amt):
    success, msg = hideout_logic.start_dismantle_job(app.save_data, s_id, code, name, yield_amt)
    col = "#00FF00" if success else "#FF0000"
    app.show_temporary_text(app.hideout_feedback_label, msg, col)
    # Reload UI to update inventory counts and slots
    _render_crafting_screen(app, s_id, level)

def _do_craft_blueprint(app, s_id, level, blueprint):
    success, msg = hideout_logic.start_blueprint_craft_job(app.save_data, s_id, blueprint)
    col = "#00FF00" if success else "#FF0000"
    app.show_temporary_text(app.hideout_feedback_label, msg, col)
    # Reload UI to update component balance and slots
    refresh_hideout_ui(app) # Updates header currency
    _render_crafting_screen(app, s_id, level)

def _collect_active_craft(app, s_id):
    import etw_hideout
    res = etw_hideout.collect_finished_craft(app.save_data, s_id)
    color = "#00FF00" if res["success"] else "#FF0000"
    app.show_temporary_text(app.hideout_feedback_label, res["msg"], color)
    refresh_hideout_ui(app)