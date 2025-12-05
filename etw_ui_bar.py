import tkinter as tk
import tkinter.messagebox
import random

# Core Imports
import etw_engine as engine
import etw_fence as fence
import etw_companions as companions
import etw_ui_town 
import etw_stats as stats
import etw_town_services as town_services
import etw_io as io
import etw_config as config
import etw_dialogue as dialogue 
import etw_bridge as bridge # Needed for scan
import etw_inventory as inventory # Needed for verification
import etw_ui_styles # Shared UI Utilities

# ----------------------------------------------------------------------
# BAR UI MODULE
# ----------------------------------------------------------------------

def build_bar_screen(app, frame):
    # 1. Header (Top)
    tk.Label(frame, text="The Salty Atom", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=5)

    # 2. Navigation
    top_nav = tk.Frame(frame, bg="#111111")
    top_nav.pack(fill="x", pady=5, padx=20)
    tk.Button(top_nav, text="Return to Town", command=app.show_town_screen, bg="#003300", fg="#00FF00", font=("Courier", 12, "bold")).pack(side="left")
    app.bar_scrip_label = tk.Label(top_nav, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.bar_scrip_label.pack(side="right")
    
    # 3. Global Feedback
    app.bar_feedback_label = tk.Label(frame, text="", fg="#00FF00", bg="#111111", font=("Courier", 10, "bold"))
    app.bar_feedback_label.pack(pady=5)
    
    # 4. Main Content
    app.bar_content_frame = tk.Frame(frame, bg="#111111")
    app.bar_content_frame.pack(fill="both", expand=True, padx=20, pady=5)

def refresh_bar_ui(app):
    for w in app.bar_content_frame.winfo_children(): w.destroy()
    current_scrip = app.save_data.get('scrip', 0)
    if hasattr(app, 'bar_scrip_label') and app.bar_scrip_label.winfo_exists():
        app.bar_scrip_label.config(text=f"Scrip: {current_scrip}")
    app.bar_feedback_label.config(text="")
    
    if not app.save_data.get("bar_unlocked", False):
        _build_bar_locked_ui(app)
    else:
        _build_bar_unlocked_ui(app)

# ----------------------------------------------------------------------
# LOCKED STATE
# ----------------------------------------------------------------------
def _build_bar_locked_ui(app):
    q_id = "bar_unlock"
    q_data = next((q for q in app.side_quests if q["id"] == q_id), None)
    
    center = tk.Frame(app.bar_content_frame, bg="#111111")
    center.pack(expand=True)
    
    if not q_data:
        tk.Label(center, text="[INN CLOSED - NO DATA]", fg="#FF0000", bg="#111111").pack()
        return

    active_side = app.save_data.get("active_side_quests", [])
    is_active = q_id in active_side
    
    status_text = "[QUEST IN PROGRESS]" if is_active else "[INN CLOSED]"
    status_col = "#FFFF00" if is_active else "#FF0000"
    
    tk.Label(center, text=status_text, fg=status_col, bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(center, text=q_data["title"], fg="#FFFFFF", bg="#111111", font=("Courier", 14, "bold")).pack(pady=5)
    desc = q_data.get("flavor_text", "")
    tk.Label(center, text=desc, fg="#AAAAAA", bg="#111111", font=("Courier", 10, "italic"), wraplength=600, justify="center").pack(pady=10)
    
    tk.Label(center, text="Requirements:", fg="#00FFFF", bg="#111111", font=("Courier", 12, "bold")).pack(pady=(10,5))
    for obj in q_data.get("objectives", []):
        tk.Label(center, text=f"- {obj}", fg="#FFFFFF", bg="#111111", font=("Courier", 11)).pack()

    if is_active:
        rep = stats.compute_reputation(app.save_data)
        met_req = (rep >= 1.0)
        status_msg = f"Current Reputation: {rep:.2f} / 1.0"
        status_col = "#00FF00" if met_req else "#FF0000"
        tk.Label(center, text=status_msg, fg=status_col, bg="#111111", font=("Courier", 10)).pack(pady=10)
        
        state = "normal" if met_req else "disabled"
        bg_col = "#004400" if met_req else "#222222"
        txt = "COMPLETE QUEST" if met_req else "Requirements Not Met"
        
        tk.Button(center, text=txt, state=state, bg=bg_col, fg="#00FF00", command=lambda: _complete_bar_quest_inline(app, center, q_data), font=("Courier", 12, "bold")).pack(pady=20)
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
        refresh_bar_ui(app)

def _complete_bar_quest_inline(app, parent_frame, q_data):
    for w in parent_frame.winfo_children(): w.destroy()
    tk.Label(parent_frame, text="ACCESS GRANTED", fg="#00FF00", bg="#111111", font=("Courier", 18, "bold")).pack(pady=20)
    msg = q_data.get("completion_text", "Done!")
    tk.Label(parent_frame, text=msg, fg="#FFFFFF", bg="#111111", font=("Courier", 12), wraplength=600, justify="center").pack(pady=10)
    if q_data["id"] in app.save_data["active_side_quests"]:
        app.save_data["active_side_quests"].remove(q_data["id"])
    app.save_data["bar_unlocked"] = True
    io.save_json(config.PATHS["save_data"], app.save_data)
    tk.Button(parent_frame, text="ENTER BAR", command=lambda: refresh_bar_ui(app), bg="#003300", fg="#00FF00", font=("Courier", 14, "bold")).pack(pady=20)

# ----------------------------------------------------------------------
# UNLOCKED STATE
# ----------------------------------------------------------------------
def _build_bar_unlocked_ui(app):
    # Configure 3-column layout for NPCs
    top_frame = tk.Frame(app.bar_content_frame, bg="#111111")
    top_frame.pack(fill="both", expand=True)
    top_frame.columnconfigure(0, weight=1, uniform="npc_col")
    top_frame.columnconfigure(1, weight=1, uniform="npc_col")
    top_frame.columnconfigure(2, weight=1, uniform="npc_col")
    
    # 1. Innkeeper
    inn_panel = tk.Frame(top_frame, bg="#1a1a1a", bd=2, relief="ridge")
    inn_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    _build_innkeeper_panel(app, inn_panel)
    
    # 2. Broker
    broker_panel = tk.Frame(top_frame, bg="#1a1a1a", bd=2, relief="ridge")
    broker_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
    _build_broker_panel(app, broker_panel)
    
    # 3. Fence (Moved up from Lounge)
    fence_panel = tk.Frame(top_frame, bg="#1a1a1a", bd=2, relief="ridge")
    fence_panel.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
    _build_fence_panel(app, fence_panel)
    
    # 4. Lounge (Bottom)
    bottom_panel = tk.Frame(app.bar_content_frame, bg="#111111", bd=2, relief="groove")
    bottom_panel.pack(fill="x", pady=10, padx=5)
    _build_lounge_panel(app, bottom_panel)

# --- INNKEEPER ---
def _build_innkeeper_panel(app, frame):
    data = dialogue.get_npc_data("innkeeper")
    tk.Label(frame, text=data.get("name", "Innkeeper"), fg="#FFD700", bg="#1a1a1a", font=("Courier", 14, "bold")).pack(pady=10)
    desc = data.get("description", "")
    tk.Label(frame, text=desc, fg="#AAAAAA", bg="#1a1a1a", font=("Courier", 10, "italic"), wraplength=200).pack(pady=5)
    
    bar_conf = io.load_json(config.PATHS["content_bar"])
    base_cost = bar_conf.get("innkeeper", {}).get("cost_scrip", 3)
    final_cost = stats.apply_economy_mult(base_cost, "cost", app.save_data)
    
    intro = dialogue.get_dialogue("innkeeper", "intro")
    
    act_row = tk.Frame(frame, bg="#1a1a1a")
    act_row.pack(pady=10)
    
    tk.Button(act_row, text="TALK", command=lambda: _open_talk_interface(app, data["name"], data["title"], intro, actions=[
        {"text": f"Rent Room ({final_cost} Scrip)", "cmd": lambda: _handle_rest(app, frame, final_cost)}
    ]), bg="#333333", fg="#FFFFFF", font=("Courier", 10)).pack(side="left", padx=5)
    
    tk.Button(act_row, text=f"RENT ({final_cost})", command=lambda: _handle_rest(app, frame, final_cost), bg="#003300", fg="#00FF00", font=("Courier", 10, "bold")).pack(side="left", padx=5)

def _handle_rest(app, parent_frame, cost):
    res = town_services.rest_at_inn(app.save_data) 
    if not res["success"]:
        app.show_temporary_text(app.bar_feedback_label, res["msg"], "#FF0000")
        return
    refresh_bar_ui(app)
    app.show_temporary_text(app.bar_feedback_label, res["msg"] + " Day Advanced.", "#00FF00")
    etw_ui_town.update_town_stats(app) 

# --- BROKER ---
def _build_broker_panel(app, frame):
    data = dialogue.get_npc_data("broker")
    tk.Label(frame, text=data.get("name", "Broker"), fg="#00BFFF", bg="#1a1a1a", font=("Courier", 14, "bold")).pack(pady=10)
    desc = data.get("description", "")
    tk.Label(frame, text=desc, fg="#AAAAAA", bg="#1a1a1a", font=("Courier", 10, "italic"), wraplength=200).pack(pady=5)
    
    intel_conf = io.load_json(config.PATHS["content_intel"])
    pool = intel_conf.get("raid_intel", [])
    known_intel = app.save_data.get("unlocked_intel", [])
    available = [i for i in pool if i["id"] not in known_intel]
    sold_out = len(available) == 0
    
    intro_text = dialogue.get_dialogue("broker", "intro")
    if sold_out: intro_text = dialogue.get_dialogue("broker", "sold_out")
        
    bar_conf = io.load_json(config.PATHS["content_bar"])
    base_cost = bar_conf.get("broker", {}).get("cost_scrip", 1)
    final_cost = stats.apply_economy_mult(base_cost, "cost", app.save_data)
    
    act_row = tk.Frame(frame, bg="#1a1a1a")
    act_row.pack(pady=10)
    
    talk_actions = []
    if not sold_out:
        talk_actions.append({"text": f"Buy Intel ({final_cost} Scrip)", "cmd": lambda: _handle_buy_intel(app, None, final_cost)})
        
    tk.Button(act_row, text="TALK", command=lambda: _open_talk_interface(app, data["name"], data["title"], intro_text, actions=talk_actions), bg="#333333", fg="#FFFFFF", font=("Courier", 10)).pack(side="left", padx=5)
    
    state = "disabled" if sold_out else "normal"
    bg_col = "#333333" if sold_out else "#003333"
    fg_col = "#888888" if sold_out else "#00FFFF"
    
    tk.Button(act_row, text=f"BUY INTEL ({final_cost})", state=state, command=lambda: _handle_buy_intel(app, frame, final_cost), bg=bg_col, fg=fg_col, font=("Courier", 10, "bold")).pack(side="left", padx=5)

def _handle_buy_intel(app, parent_frame, cost):
    if app.save_data.get("scrip", 0) < cost:
        app.show_temporary_text(app.bar_feedback_label, "Not enough Scrip.", "#FF0000")
        return
        
    res = town_services.buy_raid_intel(app.save_data) 
    
    if not res["success"]:
        app.show_temporary_text(app.bar_feedback_label, res["msg"], "#FF0000")
        if res.get("sold_out"): refresh_bar_ui(app) 
        return
    
    target_frame = parent_frame if parent_frame else app.bar_content_frame
    
    for w in target_frame.winfo_children(): w.destroy()
    
    intel_data = res["data"]
    tk.Label(target_frame, text="DOSSIER ACQUIRED", fg="#00FF00", bg="#1a1a1a", font=("Courier", 14, "bold")).pack(pady=10)
    tk.Label(target_frame, text=f"Subject: {intel_data.get('title')}", fg="#FFFF00", bg="#1a1a1a", font=("Courier", 12, "bold")).pack(pady=2)
    details = intel_data.get("text", "No Data.")
    tk.Label(target_frame, text=details, fg="#CCCCCC", bg="#1a1a1a", font=("Courier", 9), wraplength=380, justify="left").pack(pady=10, padx=10)
    tk.Button(target_frame, text="Store Intel & Return", command=lambda: refresh_bar_ui(app), bg="#003300", fg="#00FF00", font=("Courier", 10, "bold")).pack(pady=10)
    etw_ui_town.update_town_stats(app) 

# --- FENCE (NEW STANDARD WIDGET) ---
def _build_fence_panel(app, frame):
    data = dialogue.get_npc_data("fence")
    tk.Label(frame, text=data.get("name", "The Fence"), fg="#FFAA00", bg="#1a1a1a", font=("Courier", 14, "bold")).pack(pady=10)
    desc = data.get("description", "")
    tk.Label(frame, text=desc, fg="#AAAAAA", bg="#1a1a1a", font=("Courier", 10, "italic"), wraplength=200).pack(pady=5)
    
    intro = dialogue.get_dialogue("fence", "intro")
    
    act_row = tk.Frame(frame, bg="#1a1a1a")
    act_row.pack(pady=10)
    
    # Standard TALK button leading to standard dialogue
    tk.Button(act_row, text="TALK", command=lambda: _open_talk_interface(app, data["name"], data["title"], intro, actions=[
        {"text": "Let's trade.", "cmd": lambda: _start_fence_session(app)}
    ]), bg="#333333", fg="#FFFFFF", font=("Courier", 10)).pack(side="left", padx=5)
    
    # Direct Trade button
    tk.Button(act_row, text="TRADE", command=lambda: _start_fence_session(app), bg="#442200", fg="#FFAA00", font=("Courier", 10, "bold")).pack(side="left", padx=5)

def _start_fence_session(app):
    """
    Triggers inventory scan before opening the shop interface to ensure validity.
    """
    game_path = app.save_data.get("game_install_path", "")
    if game_path:
        app.show_temporary_text(app.bar_feedback_label, "Scanning Inventory...", "#FFFF00")
        bridge.trigger_inventory_scan(game_path)
        app.after(1500, lambda: _finalize_fence_entry(app))
    else:
        _open_fence_interface(app)

def _finalize_fence_entry(app):
    inventory.perform_full_inventory_sync(app.save_data)
    app.show_temporary_text(app.bar_feedback_label, "Inventory Synced.", "#00FF00")
    _open_fence_interface(app)

# --- LOUNGE ---
def _build_lounge_panel(app, frame):
    tk.Label(frame, text="The Lounge", fg="#AAAAAA", bg="#111111", font=("Courier", 10, "bold")).pack(anchor="nw", padx=5, pady=2)
    seat_frame = tk.Frame(frame, bg="#111111")
    seat_frame.pack(fill="x", pady=5)
    _build_feature_placeholder(seat_frame, "Dice Table", "Gambling [Coming Soon]")
    
    g_state = app.save_data.get("global_companion_state", {})
    bar_slots = g_state.get("bar_slots", [None, None, None])
    day_cycle = app.save_data.get("day_cycle", 1)
    rnd_npcs = io.load_json(config.PATHS["content_random_npcs"])
    for i, companion_id in enumerate(bar_slots):
        if companion_id:
            _build_companion_seat(app, seat_frame, companion_id)
        else:
            _build_random_npc_seat(app, seat_frame, i, day_cycle, rnd_npcs)

def _build_companion_seat(app, parent, companion_id):
    roster = companions.load_companion_roster()
    c_def = roster.get(companion_id)
    if not c_def: return
    f = tk.Frame(parent, bg="#222222", bd=1, relief="solid", width=110, height=70)
    f.pack(side="left", padx=10, pady=5)
    f.pack_propagate(False)
    tk.Label(f, text=c_def["name"], fg="#00FF00", bg="#222222", font=("Courier", 9, "bold")).pack(pady=(5,0))
    tk.Label(f, text=c_def["archetype"], fg="#AAAAAA", bg="#222222", font=("Courier", 8)).pack()
    tk.Button(f, text="TALK", command=lambda: _open_companion_interaction(app, companion_id, c_def), bg="#003300", fg="#00FF00", font=("Courier", 8, "bold"), width=8).pack(side="bottom", pady=5)

def _build_random_npc_seat(app, parent, slot_idx, day, npc_data):
    seed_key = f"{day}_{slot_idx}"
    random.seed(seed_key)
    f_name = random.choice(npc_data.get("first_names", ["Stranger"]))
    l_name = random.choice(npc_data.get("last_names", ["Doe"]))
    descriptor = random.choice(npc_data.get("descriptors", ["Wastelander"]))
    flavor_text = random.choice(npc_data.get("dialogue", ["..."]))
    random.seed()
    f = tk.Frame(parent, bg="#222222", bd=1, relief="solid", width=110, height=70)
    f.pack(side="left", padx=10, pady=5)
    f.pack_propagate(False)
    tk.Label(f, text=f"{f_name}", fg="#FFFFFF", bg="#222222", font=("Courier", 9, "bold")).pack(pady=(5,0))
    tk.Label(f, text=descriptor, fg="#555555", bg="#222222", font=("Courier", 7)).pack()
    full_name = f"{f_name} {l_name}"
    
    tk.Button(f, text="TALK", command=lambda: _open_talk_interface(app, full_name, descriptor, flavor_text), bg="#333333", fg="#FFFFFF", font=("Courier", 8, "bold"), width=8).pack(side="bottom", pady=5)

def _build_feature_placeholder(parent, title, status):
    f = tk.Frame(parent, bg="#222222", bd=1, relief="solid", width=110, height=70)
    f.pack(side="left", padx=10, pady=5)
    f.pack_propagate(False)
    tk.Label(f, text=title, fg="#FFFFFF", bg="#222222", font=("Courier", 9, "bold")).pack(pady=(5,0))
    tk.Label(f, text=status, fg="#555555", bg="#222222", font=("Courier", 8), wraplength=100).pack(expand=True)

# --- STANDARDIZED TALK INTERFACE ---
def _open_talk_interface(app, name, descriptor, flavor_text, actions=None):
    """
    Standardized screen for NPC interaction.
    """
    for w in app.bar_content_frame.winfo_children(): w.destroy()
    
    tk.Label(app.bar_content_frame, text=f"Talking to: {name}", fg="#00FF00", bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(app.bar_content_frame, text=f"({descriptor})", fg="#AAAAAA", bg="#111111", font=("Courier", 10)).pack()
    tk.Label(app.bar_content_frame, text=f"\"{flavor_text}\"", fg="#FFFFFF", bg="#111111", font=("Courier", 12, "italic"), wraplength=500, justify="center").pack(pady=20)
    
    btn_frame = tk.Frame(app.bar_content_frame, bg="#111111")
    btn_frame.pack(pady=20)
    
    if actions:
        for act in actions:
            tk.Button(btn_frame, text=act["text"], command=act["cmd"], bg="#004400", fg="#FFFF00", font=("Courier", 11)).pack(side="left", padx=10)
            
    tk.Button(btn_frame, text="Leave", command=lambda: refresh_bar_ui(app), bg="#330000", fg="#FFFFFF", font=("Courier", 11)).pack(side="left", padx=10)

def _open_companion_interaction(app, companion_id, c_def):
    q_id = f"recruitment_{companion_id}"
    is_active = q_id in app.save_data.get("active_side_quests", [])
    actions = []
    
    flavor = c_def["personality"]
    if c_def.get("flavor_recruit"): flavor = c_def["flavor_recruit"]
    
    if is_active:
        if _is_quest_complete(app, q_id):
            _render_recruitment_completion_dialog(app, companion_id, c_def)
            return
        else:
            flavor = "I'm still waiting on you to finish that job."
    else:
        actions.append({
            "text": "Offer Contract (Recruit)", 
            "cmd": lambda: _accept_recruit_quest(app, companion_id)
        })
        
    _open_talk_interface(app, c_def['name'], c_def['archetype'], flavor, actions)

def _is_quest_complete(app, q_id):
    if "quest_progress" not in app.save_data: return False
    prog = app.save_data["quest_progress"].get(str(q_id), [])
    return len(prog) > 0 and all(prog)

def _accept_recruit_quest(app, companion_id):
    quest = engine.generate_companion_quest(app.save_data, companion_id, "recruitment")
    if quest:
        app.show_temporary_text(app.bar_feedback_label, "Recruitment Quest Started!", "#00FF00")
        refresh_bar_ui(app)
        etw_ui_town.update_town_stats(app) 
    else:
        app.show_temporary_text(app.bar_feedback_label, "Error starting quest.", "#FF0000")

def _render_recruitment_completion_dialog(app, companion_id, c_def):
    for w in app.bar_content_frame.winfo_children(): w.destroy()
    tk.Label(app.bar_content_frame, text="CONTRACT FULFILLED", fg="#00FF00", bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(app.bar_content_frame, text=f"\"{c_def['name']}: You held up your end. I'm ready to work.\"", fg="#FFFFFF", bg="#111111", font=("Courier", 12, "italic"), wraplength=500, justify="center").pack(pady=20)
    tk.Button(app.bar_content_frame, text="FINALIZE RECRUITMENT", command=lambda: _finalize_recruit(app, companion_id), bg="#004400", fg="#FFFF00", font=("Courier", 14, "bold")).pack(pady=20)

def _finalize_recruit(app, companion_id):
    companions.complete_recruitment(app.save_data, companion_id)
    q_id = f"recruitment_{companion_id}"
    if q_id in app.save_data.get("active_side_quests", []):
        app.save_data["active_side_quests"].remove(q_id)
    io.save_json(config.PATHS["save_data"], app.save_data)
    app.show_temporary_text(app.bar_feedback_label, "Recruited!", "#00FF00")
    refresh_bar_ui(app)
    etw_ui_town.update_town_stats(app) 

# --- FENCE INTERFACE ---
def _open_fence_interface(app):
    for w in app.bar_content_frame.winfo_children(): w.destroy()
    import etw_fence as fence
    shop_data = fence.load_fence_shop()
    if not shop_data: shop_data = fence.refresh_shop(app.save_data)
        
    app.fence_budget_var = tk.StringVar()
    budget = shop_data.get("scrip_budget", 0)
    max_b = shop_data.get("max_budget", 0)
    app.fence_budget_var.set(f"Fence Budget: {budget}/{max_b} Scrip")
    
    header_frame = tk.Frame(app.bar_content_frame, bg="#111111")
    header_frame.pack(fill="x", pady=10)
    tk.Label(header_frame, text="BLACK MARKET FENCE", fg="#FFAA00", bg="#111111", font=("Courier", 20, "bold")).pack(side="left")
    app.fence_budget_lbl = tk.Label(header_frame, textvariable=app.fence_budget_var, fg="#00FF00", bg="#111111", font=("Courier", 12))
    app.fence_budget_lbl.pack(side="right")

    action_row = tk.Frame(app.bar_content_frame, bg="#111111")
    action_row.pack(fill="x", pady=5)
    base_cost = fence.get_refresh_cost(app.save_data)
    cost = stats.apply_economy_mult(base_cost, "cost", app.save_data)
    
    tk.Button(action_row, text=f"REFRESH OFFERS ({cost} Caps)", command=lambda: _fence_refresh_action(app, cost), bg="#333300", fg="#FFFF00", font=("Courier", 10, "bold")).pack(side="right")
    tk.Button(action_row, text="< EXIT TRADING", command=lambda: refresh_bar_ui(app), bg="#330000", fg="#FFFFFF", font=("Courier", 10)).pack(side="left")

    split_frame = tk.Frame(app.bar_content_frame, bg="#111111")
    split_frame.pack(fill="both", expand=True, pady=10)
    split_frame.columnconfigure(0, weight=1, uniform="group1")
    split_frame.columnconfigure(1, weight=1, uniform="group1")
    
    buy_col = tk.Frame(split_frame, bg="#1a1a1a", bd=2, relief="ridge")
    buy_col.grid(row=0, column=0, sticky="nsew", padx=5)
    tk.Label(buy_col, text="BUY ITEMS (Fence Selling)", fg="#00FFFF", bg="#1a1a1a", font=("Courier", 12, "bold")).pack(pady=5)
    
    sell_col = tk.Frame(split_frame, bg="#1a1a1a", bd=2, relief="ridge")
    sell_col.grid(row=0, column=1, sticky="nsew", padx=5)
    tk.Label(sell_col, text="SELL ITEMS (Fence Buying)", fg="#FF00FF", bg="#1a1a1a", font=("Courier", 12, "bold")).pack(pady=5)
    
    for i, item in enumerate(shop_data.get("buy_slots", [])): _render_fence_slot(app, buy_col, item, i, "buy")
    for i, item in enumerate(shop_data.get("sell_slots", [])): _render_fence_slot(app, sell_col, item, i, "sell")

def _render_fence_slot(app, parent, item, index, mode):
    f = tk.Frame(parent, bg="#222222", bd=1, relief="solid")
    f.pack(fill="x", padx=5, pady=2)
    if not item:
        tk.Label(f, text="--- EMPTY ---", fg="#555555", bg="#222222", font=("Courier", 10)).pack(pady=5)
        return
    name = item["name"]
    qty = item["qty"]
    total_cost = item["total_scrip_cost"]
    info = tk.Frame(f, bg="#222222")
    info.pack(side="left", fill="x", expand=True, padx=5)
    
    # Store label reference to update color later
    name_lbl = tk.Label(info, text=f"{name} (x{qty})", fg="#FFFFFF", bg="#222222", font=("Courier", 10, "bold"))
    name_lbl.pack(anchor="w")
    
    btn_txt = f"{total_cost} Scrip"
    cmd = None; btn_bg = "#333333"; btn_fg = "#FFFFFF"
    
    if mode == "buy":
        cmd = lambda: _fence_buy_click(app, index)
        can_afford = app.save_data.get("scrip", 0) >= total_cost
        btn_bg = "#004400" if can_afford else "#330000"
        btn_fg = "#00FF00" if can_afford else "#880000"
    else:
        # Check Inventory for Sell Button Color AND Name Color
        game_path = app.save_data.get("game_install_path", "")
        char_data = inventory.get_character_data(game_path)
        current_inv = char_data.get("inventory", [])
        
        has_item = False
        req_code = item.get("code", "")
        req_suffix = req_code[-6:] if len(req_code) >= 6 else req_code
        req_qty = item.get("qty", 1)
        
        for inv_item in current_inv:
            inv_code = inv_item.get("code", "")
            inv_suffix = inv_code[-6:] if len(inv_code) >= 6 else inv_code
            if (inv_code == req_code or inv_suffix == req_suffix) and inv_item.get("qty", 0) >= req_qty:
                has_item = True
                break
        
        cmd = lambda: _fence_sell_click(app, index, total_cost, item)
        import etw_fence as fence
        shop = fence.load_fence_shop()
        budget = shop.get("scrip_budget", 0) if shop else 0
        has_budget = budget >= total_cost
        
        if not has_item:
            btn_bg = "#550000" # Red bg for missing item
            btn_fg = "#FFaaaa"
            name_lbl.config(fg="#FF4444") # Red text for missing item name
        elif not has_budget:
            btn_bg = "#330000"
            btn_fg = "#888888"
        else:
            btn_bg = "#440044"
            btn_fg = "#FF00FF"
        
        # Tooltip for missing status
        tip_content = []
        if not has_item:
            tip_content.append((f"Missing: {name} (x{qty})", "#FF0000"))
        else:
            tip_content.append((f"Sell: {name} (x{qty})", "#FFFFFF"))
            
    btn = tk.Button(f, text=btn_txt, command=cmd, bg=btn_bg, fg=btn_fg, width=10, font=("Courier", 9, "bold"))
    btn.pack(side="right", padx=5, pady=5)
    
    # REPLACED LOCAL USAGE
    if mode != "buy":
        etw_ui_styles.create_tooltip(btn, tip_content)

def _fence_refresh_action(app, cost):
    engine._process_game_commands([f"player.removeitem 0000000F {cost}"])
    fence.refresh_shop(app.save_data)
    app.show_temporary_text(app.bar_feedback_label, "Inventory Refreshed!", "#00FF00")
    _start_fence_session(app) # Re-scan to keep things fresh

def _fence_buy_click(app, index):
    success, msg = fence.perform_fence_buy(app.save_data, index)
    col = "#00FF00" if success else "#FF0000"
    app.show_temporary_text(app.bar_feedback_label, msg, col)
    if success:
        etw_ui_town.update_town_stats(app) 
        app.bar_scrip_label.config(text=f"Scrip: {app.save_data.get('scrip', 0)}")
        _open_fence_interface(app)

def _fence_sell_click(app, index, payout, item_data):
    # Verify Inventory BEFORE Selling
    req_item = {"code": item_data["code"], "qty": item_data["qty"], "name": item_data["name"]}
    
    result = inventory.verify_and_remove_items(app.save_data, [req_item])
    
    if not result["success"]:
        app.show_temporary_text(app.bar_feedback_label, f"Missing: {item_data['name']}", "#FF0000")
        return

    import etw_fence as fence_mod
    shop = fence_mod.load_fence_shop()
    if not shop: return
    
    slots = shop.get("sell_slots", [])
    if index < 0 or index >= len(slots): return
    
    # Update Stats
    app.save_data["scrip"] += payout
    shop["scrip_budget"] -= payout
    slots[index] = None
    shop["sell_slots"] = slots
    fence_mod.save_fence_shop(shop)
    
    io.save_json(config.PATHS["save_data"], app.save_data)
    
    app.show_temporary_text(app.bar_feedback_label, f"Sold for {payout} Scrip", "#00FF00")
    
    # Refresh UI
    etw_ui_town.update_town_stats(app) 
    app.bar_scrip_label.config(text=f"Scrip: {app.save_data.get('scrip', 0)}")
    app.fence_budget_var.set(f"Fence Budget: {shop['scrip_budget']}/{shop['max_budget']} Scrip")
    _open_fence_interface(app)