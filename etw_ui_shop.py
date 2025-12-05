import tkinter as tk
import os
import re
import time
import etw_engine as engine
import etw_tasks as tasks 
import etw_ui_town 
import etw_inventory as inventory # Import Manager for Source of Truth
import etw_stats as stats # NEW: Import stats module for economy functions
import etw_dialogue as dialogue # NEW
import etw_loot as loot # NEW: For Tier lookups
import etw_bridge as bridge # NEW: For polling

# ----------------------------------------------------------------------
# SHOP UI MODULE
# ----------------------------------------------------------------------

def build_shop_screen(app, frame):
    # 1. Header (Top)
    tk.Label(frame, text="Stop n' Shop", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=5)

    # 2. Navigation Bar (Underneath Header)
    nav_frame = tk.Frame(frame, bg="#111111")
    nav_frame.pack(fill="x", pady=5, padx=20)
    
    # Return Button (Left)
    tk.Button(nav_frame, text="Return to Town", command=app.show_town_screen, bg="#003300", fg="#00FF00", font=("Courier", 12, "bold")).pack(side="left")
    
    # Scrip Display (Right)
    app.shop_scrip_label = tk.Label(nav_frame, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.shop_scrip_label.pack(side="right")

    # 3. Feedback Label
    app.shop_feedback_label = tk.Label(frame, text="", fg="#00FF00", bg="#111111", font=("Courier", 10, "bold"))
    app.shop_feedback_label.pack(pady=(0, 5))
    
    # 4. Main Content Container
    app.shop_content_frame = tk.Frame(frame, bg="#111111")
    app.shop_content_frame.pack(fill="both", expand=True, padx=10, pady=5)

def refresh_shop_ui(app):
    for w in app.shop_content_frame.winfo_children(): w.destroy()
    
    current_scrip = app.save_data.get('scrip', 0)
    if hasattr(app, 'shop_scrip_label'):
        app.shop_scrip_label.config(text=f"Scrip: {current_scrip}")
    app.shop_feedback_label.config(text="") 
    
    if not app.save_data.get("shop_unlocked", False):
        _build_shop_locked_ui(app)
    else:
        _build_shop_unlocked_ui(app)

# ----------------------------------------------------------------------
# LOCKED STATE
# ----------------------------------------------------------------------
def _build_shop_locked_ui(app):
    q_id = "shop_unlock"
    quest_data = next((q for q in app.side_quests if q["id"] == q_id), None)
    
    center = tk.Frame(app.shop_content_frame, bg="#111111")
    center.pack(expand=True)
    
    if not quest_data:
        tk.Label(center, text="[SHOP CLOSED]", fg="#FF0000", bg="#111111").pack()
        return

    active_side = app.save_data.get("active_side_quests", [])
    is_active = q_id in active_side
    
    status_text = "[QUEST IN PROGRESS]" if is_active else "[SHOP LOCKED]"
    status_col = "#FFFF00" if is_active else "#FF0000"
    
    tk.Label(center, text=status_text, fg=status_col, bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(center, text=quest_data["title"], fg="#FFFFFF", bg="#111111", font=("Courier", 14, "bold")).pack(pady=5)
    
    desc = quest_data.get("flavor_text", "")
    tk.Label(center, text=desc, fg="#AAAAAA", bg="#111111", font=("Courier", 12), wraplength=600, justify="center").pack(pady=10)
    
    if is_active:
        progress = app.save_data.get("quest_progress", {}).get(q_id, [])
        all_done = (len(progress) > 0 and all(progress))
        
        if all_done:
            tk.Button(center, text="COMPLETE QUEST", command=lambda: _complete_shop_unlock_inline(app, center, quest_data), bg="#004400", fg="#00FF00", font=("Courier", 12, "bold")).pack(pady=20)
        else:
            tk.Label(center, text="(Check Quest Log to track progress)", fg="#555555", bg="#111111", font=("Courier", 10)).pack(pady=20)
    else:
        tk.Button(center, text="ACCEPT QUEST", command=lambda: _accept_static_side_quest(app, q_id), bg="#003300", fg="#00FF00", font=("Courier", 14, "bold")).pack(pady=20)

def _accept_static_side_quest(app, q_id):
    if "active_side_quests" not in app.save_data: app.save_data["active_side_quests"] = []
    if q_id not in app.save_data["active_side_quests"]:
        app.save_data["active_side_quests"].append(q_id)
        
        q_data = next((q for q in app.side_quests if q["id"] == q_id), None)
        count = len(q_data.get("objectives", [])) if q_data else 1
        
        if "quest_progress" not in app.save_data: app.save_data["quest_progress"] = {}
        app.save_data["quest_progress"][q_id] = [False] * count
        
        engine.save_save_data(app.save_data)
        refresh_shop_ui(app)

def _complete_shop_unlock_inline(app, parent_frame, q_data):
    for w in parent_frame.winfo_children(): w.destroy()
    
    tk.Label(parent_frame, text="ACCESS GRANTED", fg="#00FF00", bg="#111111", font=("Courier", 18, "bold")).pack(pady=20)
    msg = q_data.get("completion_text", "Done!")
    tk.Label(parent_frame, text=msg, fg="#FFFFFF", bg="#111111", font=("Courier", 12), wraplength=600, justify="center").pack(pady=10)
    
    if q_data["id"] in app.save_data["active_side_quests"]:
        app.save_data["active_side_quests"].remove(q_data["id"])
    app.save_data["shop_unlocked"] = True
    
    engine.save_save_data(app.save_data)
    
    tk.Button(parent_frame, text="ENTER SHOP", command=lambda: refresh_shop_ui(app), bg="#003300", fg="#00FF00", font=("Courier", 14, "bold")).pack(pady=20)

# ----------------------------------------------------------------------
# UNLOCKED STATE
# ----------------------------------------------------------------------
def _build_shop_unlocked_ui(app):
    # Shopkeeper Panel
    top_panel = tk.Frame(app.shop_content_frame, bg="#1a1a1a", bd=2, relief="ridge")
    top_panel.pack(fill="x", pady=(0, 10), padx=5)
    _build_shopkeeper_widget(app, top_panel)
    
    # Items List
    bottom_panel = tk.Frame(app.shop_content_frame, bg="#111111")
    bottom_panel.pack(fill="both", expand=True, padx=5)
    
    items = app.shop_items
    if not items:
        tk.Label(bottom_panel, text="Shop is empty.", fg="#555555", bg="#111111", font=("Courier", 12)).pack()
    else:
        for item in items:
            if item.get("type") == "upgrade":
                _build_upgrade_row(app, bottom_panel, item)
            else:
                _build_shop_item_row(app, bottom_panel, item)

def _build_shopkeeper_widget(app, frame):
    data = dialogue.get_npc_data("shopkeeper")
    tk.Label(frame, text=data.get("name", "Shopkeeper"), fg="#FFD700", bg="#1a1a1a", font=("Courier", 14, "bold")).pack(pady=5)
    
    greeting = dialogue.get_dialogue("shopkeeper", "greeting")
    tk.Label(frame, text=f"\"{greeting}\"", fg="#FFFFFF", bg="#1a1a1a", font=("Courier", 11)).pack(pady=5)
    
    # Actions Row
    act_row = tk.Frame(frame, bg="#1a1a1a")
    act_row.pack(pady=10)
    
    # TALK Button (Nests quests)
    tk.Button(act_row, text="TALK", command=lambda: _open_shopkeeper_talk(app), bg="#333333", fg="#FFFFFF", font=("Courier", 10)).pack(side="left", padx=5)
    
    # Direct Access to Insurance if Unlocked
    if app.save_data.get("insurance_unlocked", False):
        tk.Button(act_row, text="ASSET PROTECTION", command=lambda: _open_insurance_ui(app), bg="#003355", fg="#00FFFF", font=("Courier", 10, "bold")).pack(side="left", padx=5)

def _open_shopkeeper_talk(app):
    # Replaces content with Talk Interface
    for w in app.shop_content_frame.winfo_children(): w.destroy()
    
    data = dialogue.get_npc_data("shopkeeper")
    intro = dialogue.get_dialogue("shopkeeper", "intro")
    
    tk.Label(app.shop_content_frame, text=f"Talking to: {data['name']}", fg="#00FF00", bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(app.shop_content_frame, text=f"\"{intro}\"", fg="#FFFFFF", bg="#111111", font=("Courier", 12, "italic")).pack(pady=20)
    
    btn_frame = tk.Frame(app.shop_content_frame, bg="#111111")
    btn_frame.pack(pady=10)
    
    # Insurance Quest Logic
    if not app.save_data.get("insurance_unlocked", False):
        q_id = "insurance_unlock"
        active_quests = app.save_data.get("active_side_quests", [])
        
        if q_id in active_quests:
            progress = app.save_data.get("quest_progress", {}).get(q_id, [])
            if len(progress) > 0 and all(progress):
                complete_txt = dialogue.get_dialogue("shopkeeper", "insurance_complete")
                tk.Button(btn_frame, text=complete_txt, 
                          command=lambda: _complete_insurance_unlock_inline(app, q_id), 
                          bg="#004400", fg="#FFFF00", font=("Courier", 11)).pack(fill="x", pady=5)
            else:
                tk.Label(btn_frame, text="[Contract In Progress: Protecting Assets]", fg="#FFFF00", bg="#111111", font=("Courier", 10)).pack(pady=5)
        else:
            inquiry = dialogue.get_dialogue("shopkeeper", "insurance_start")
            tk.Button(btn_frame, text=inquiry, 
                      command=lambda: _trigger_insurance_quest(app), 
                      bg="#333333", fg="#00FFFF", font=("Courier", 11)).pack(fill="x", pady=5)
    
    # Generic Leave
    leave_txt = dialogue.get_dialogue("shopkeeper", "leave")
    tk.Button(btn_frame, text=leave_txt, command=lambda: refresh_shop_ui(app), bg="#003300", fg="#00FF00", font=("Courier", 12)).pack(pady=20)

def _complete_insurance_unlock_inline(app, q_id):
    # Need to load the quest data if it's dynamically generated
    q_data = next((q for q in app.save_data.get("generated_side_quests", []) if q["id"] == q_id), None)
    
    if q_id in app.save_data["active_side_quests"]:
        app.save_data["active_side_quests"].remove(q_id)
    app.save_data["insurance_unlocked"] = True
    
    engine.save_save_data(app.save_data)
    
    unlocked_txt = dialogue.get_dialogue("shopkeeper", "insurance_unlocked")
    app.show_temporary_text(app.shop_feedback_label, unlocked_txt, "#00FF00")
    refresh_shop_ui(app)

def _trigger_insurance_quest(app):
    q_id = "insurance_unlock"
    
    flavor = dialogue.get_dialogue("shopkeeper", "insurance_intro")
    
    quest_obj_params = {
        "id": q_id,
        "title": "Protecting Assets",
        "flavor_text": flavor,
        "difficulty": "medium", 
        "reward": { "unlocks_feature": "insurance" },
        "objectives": [] 
    }
    
    import etw_task_generator as task_gen # Local import to resolve dependency
    target_task = task_gen.generate_task(app.save_data, force_difficulty="medium")
    
    if not target_task: 
        app.show_temporary_text(app.shop_feedback_label, "Error: Could not generate insurance task.", "#FF0000")
        return

    # Extract text descriptions for Side Quest display
    obj_list = []
    for o in target_task["objectives"]: obj_list.append(o[1])
    quest_obj_params["objectives"] = obj_list
    quest_obj_params["raw_objectives"] = target_task["objectives"] 
    
    # Update Save Data structures
    if "generated_side_quests" not in app.save_data: app.save_data["generated_side_quests"] = []
    app.save_data["generated_side_quests"] = [q for q in app.save_data["generated_side_quests"] if q["id"] != q_id]
    app.save_data["generated_side_quests"].append(quest_obj_params)
    
    if "active_side_quests" not in app.save_data: app.save_data["active_side_quests"] = []
    app.save_data["active_side_quests"].append(q_id)
    
    if "quest_progress" not in app.save_data: app.save_data["quest_progress"] = {}
    app.save_data["quest_progress"][q_id] = [False] * len(obj_list)
    
    engine.save_save_data(app.save_data)
    app.show_temporary_text(app.shop_feedback_label, "Quest Started: Protecting Assets", "#FF00FF")
    _open_shopkeeper_talk(app)

# ----------------------------------------------------------------------
# INSURANCE UI
# ----------------------------------------------------------------------
def _open_insurance_ui(app):
    """
    Opens Insurance UI.
    Uses Non-Blocking Polling for Inventory Scan.
    """
    game_path = app.save_data.get("game_install_path", "")
    if not game_path: return
    
    # 1. Trigger Scan
    bridge.trigger_inventory_scan(game_path) # Use inventory scan for items
    app.shop_feedback_label.config(text="Scanning Inventory... Please Wait...")
    
    # 2. Start Polling
    app.after(100, lambda: _poll_insurance_scan(app, time.time()))

def _poll_insurance_scan(app, start_time):
    game_path = app.save_data.get("game_install_path", "")
    
    # NON-BLOCKING READ
    # Note: Inventory scan uses same file as baseline (etw_baseline) per config
    result = bridge.read_baseline_scan(game_path, blocking=False)
    
    if result:
        # SUCCESS
        _finalize_insurance_scan(app)
    else:
        # TIMEOUT CHECK
        elapsed = time.time() - start_time
        if elapsed > 15.0:
            app.shop_feedback_label.config(text="Scan Timeout (Game Paused?)", fg="#FF0000")
        else:
            # RETRY
            app.after(100, lambda: _poll_insurance_scan(app, start_time))

def _finalize_insurance_scan(app):
    # 3. Parse & Update Source of Truth
    inventory.perform_full_inventory_sync(app.save_data)
    app.shop_feedback_label.config(text="")
    _render_insurance_screen(app)

def _get_item_tier_cost(item_code):
    """
    Calculates insurance cost based on rarity tier in loot DB.
    """
    pool = loot.get_loot_pool_cached()["all"]
    # Check full code first, then suffix
    target = next((i for i in pool if i.get("code") == item_code), None)
    if not target:
        suffix = item_code[-6:] if len(item_code) >= 6 else item_code
        target = next((i for i in pool if i.get("code", "").endswith(suffix)), None)
    
    if not target: return 5 # Default fallback
    
    rarity = target.get("rarity", "tier_1")
    if rarity == "tier_1": return 2
    if rarity == "tier_2": return 4
    if rarity == "tier_3": return 7
    if rarity == "tier_4": return 10
    
    return 5

def _render_insurance_screen(app):
    for w in app.shop_content_frame.winfo_children(): w.destroy()
    
    tk.Label(app.shop_content_frame, text="ASSET PROTECTION", fg="#00FFFF", bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Label(app.shop_content_frame, text="Insured items are recovered after death.\nOne-time use (expires after next raid).", fg="#AAAAAA", bg="#111111", font=("Courier", 10)).pack(pady=5)
    
    list_frame = tk.Frame(app.shop_content_frame, bg="#111111")
    list_frame.pack(fill="both", expand=True, padx=10)
    
    # READ FROM SOURCE OF TRUTH (JSON)
    game_path = app.save_data.get("game_install_path", "")
    char_data = inventory.get_character_data(game_path)
    
    inv_list = char_data.get("inventory", [])
    items_found = []
    
    # Filter for Weapon/Armor
    for item in inv_list:
        cat = item.get("category", "misc")
        if cat in ["weapon", "armor"]:
            cost = _get_item_tier_cost(item["code"])
            items_found.append({
                "code": item["code"],
                "name": item["name"],
                "type": cat,
                "cost": cost
            })
    
    if not items_found:
        tk.Label(list_frame, text="No eligible items (Weapons/Armor) found in stored inventory.", fg="#555555", bg="#111111").pack(pady=20)
        tk.Label(list_frame, text="(Try scanning again if items are missing)", fg="#333333", bg="#111111", font=("Courier", 8)).pack()
    else:
        canvas = tk.Canvas(list_frame, bg="#111111", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#111111")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        insured_list = app.save_data.get("insured_items", [])
        
        for item in items_found:
            row = tk.Frame(scrollable_frame, bg="#222222", bd=1, relief="solid")
            row.pack(fill="x", pady=1)
            
            is_insured = item["code"] in insured_list
            status_col = "#00FF00" if is_insured else "#555555"
            
            tk.Label(row, text=f"[{item['type'][0].upper()}]", fg="#AAAAAA", bg="#222222", width=4).pack(side="left")
            tk.Label(row, text=item["name"], fg=status_col, bg="#222222", font=("Courier", 10)).pack(side="left", padx=5)
            
            if is_insured:
                tk.Button(row, text="REMOVE", command=lambda c=item["code"], p=item["cost"]: _toggle_insurance(app, c, p, False), bg="#550000", fg="#FF0000", font=("Courier", 8)).pack(side="right", padx=5)
                tk.Label(row, text="INSURED", fg="#00FF00", bg="#222222", font=("Courier", 10, "bold")).pack(side="right", padx=10)
            else:
                tk.Button(row, text=f"INSURE ({item['cost']})", command=lambda c=item["code"], p=item["cost"]: _toggle_insurance(app, c, p, True), bg="#003300", fg="#00FF00", font=("Courier", 8)).pack(side="right", padx=5)

    tk.Button(app.shop_content_frame, text="Done", command=lambda: refresh_shop_ui(app), bg="#333333", fg="#FFFFFF").pack(pady=10)

def _toggle_insurance(app, item_code, price, enable):
    if enable:
        if app.save_data.get("scrip", 0) < price:
            app.show_temporary_text(app.shop_feedback_label, "Not enough Scrip!", "#FF0000")
            return
        app.save_data["scrip"] -= price
        if "insured_items" not in app.save_data: app.save_data["insured_items"] = []
        if item_code not in app.save_data["insured_items"]:
            app.save_data["insured_items"].append(item_code)
    else:
        # Removal does not refund scrip
        if item_code in app.save_data.get("insured_items", []):
            app.save_data["insured_items"].remove(item_code)
            
    engine.save_save_data(app.save_data)
    
    # FIX: Immediate UI Refresh for Scrip Header
    if hasattr(app, 'shop_scrip_label'):
        app.shop_scrip_label.config(text=f"Scrip: {app.save_data['scrip']}")
        
    _render_insurance_screen(app)

# ----------------------------------------------------------------------
# STANDARD SHOP ITEMS
# ----------------------------------------------------------------------
def _build_upgrade_row(app, parent, item_data):
    if item_data["id"] == "upgrade_task_slot":
        current_slots = app.save_data.get("unlocked_task_slots", 1)
        if current_slots >= 5:
            _render_sold_out_row(parent, "Contract Slot Upgrade (MAX)")
            return
        cost = tasks.get_next_slot_cost(app.save_data)
        if cost is None: return 
        _render_item_row_widget(app, parent, item_data["name"], item_data["description"], cost, 0, lambda l: _purchase_slot_upgrade(app, cost, current_slots + 1, l), None)

    elif item_data["id"] == "upgrade_task_pool":
        current_pool = app.save_data.get("unlocked_task_pool_size", 3)
        if current_pool >= 8:
            _render_sold_out_row(parent, "Contract Board Expansion (MAX)")
            return
        cost = tasks.get_next_pool_cost(app.save_data)
        if cost is None: return
        _render_item_row_widget(app, parent, item_data["name"], item_data["description"], cost, 0, lambda l: _purchase_pool_upgrade(app, cost, current_pool + 1, l), None)

def _render_sold_out_row(parent, name):
    f = tk.Frame(parent, bg="#222222", bd=1, relief="ridge")
    f.pack(fill="x", padx=5, pady=4)
    tk.Label(f, text=name, fg="#555555", bg="#222222", font=("Courier", 12, "bold")).pack(side="left", padx=10, pady=5)
    tk.Label(f, text="SOLD OUT", fg="#FF0000", bg="#222222", font=("Courier", 12, "bold")).pack(side="right", padx=10)

def _build_shop_item_row(app, parent, item):
    base_scrip = item.get('cost_scrip', 0)
    base_caps = item.get('cost_caps', 0)
    
    # FIX: Use stats.apply_economy_mult directly
    final_scrip = stats.apply_economy_mult(base_scrip, "cost", app.save_data) if base_scrip else 0
    final_caps = stats.apply_economy_mult(base_caps, "cost", app.save_data) if base_caps else 0
    
    owned = None
    inv_key = item.get("inventory_key")
    if inv_key:
        owned = app.save_data.get("inventory", {}).get(inv_key, 0)
    
    _render_item_row_widget(app, parent, item["name"], item.get("description", ""), final_scrip, final_caps, lambda l: _purchase_item(app, item, final_scrip, final_caps, l), owned)

def _render_item_row_widget(app, parent, name, desc, cost_scrip, cost_caps, cmd_callback, owned_count=None):
    f = tk.Frame(parent, bg="#222222", bd=1, relief="ridge")
    f.pack(fill="x", padx=5, pady=4)
    
    info_frame = tk.Frame(f, bg="#222222")
    info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)
    tk.Label(info_frame, text=name, fg="#FFFFFF", bg="#222222", font=("Courier", 12, "bold")).pack(anchor="w")
    desc_wrap = app.current_wrap_width - 400 
    tk.Label(info_frame, text=desc, fg="#AAAAAA", bg="#222222", font=("Courier", 10), wraplength=desc_wrap, justify="left").pack(anchor="w")
    
    btn_frame = tk.Frame(f, bg="#222222")
    btn_frame.pack(side="right", padx=10)
    
    cost_str = []
    if cost_scrip > 0: cost_str.append(f"{cost_scrip} Scrip")
    if cost_caps > 0: cost_str.append(f"{cost_caps} Caps")
    
    count_str = ""
    if owned_count is not None:
        count_str = f" (Owned: x{owned_count})"
        
    tk.Label(btn_frame, text=" + ".join(cost_str) + count_str, fg="#FFD700", bg="#222222", font=("Courier", 11)).pack(anchor="e")
    
    action_row = tk.Frame(btn_frame, bg="#222222")
    action_row.pack(anchor="e", pady=(2, 0))
    status_lbl = tk.Label(action_row, text="", bg="#222222", font=("Courier", 9, "bold"))
    status_lbl.pack(side="left", padx=(0, 5))
    tk.Button(action_row, text="BUY", command=lambda: cmd_callback(status_lbl), bg="#003300", fg="#00FF00", font=("Courier", 10, "bold")).pack(side="left")

# ----------------------------------------------------------------------
# PURCHASE LOGIC
# ----------------------------------------------------------------------
def _flash_status(lbl, text, color):
    lbl.config(text=text, fg=color)
    lbl.after(2000, lambda: lbl.config(text=""))

def _purchase_slot_upgrade(app, cost, new_level, lbl):
    if app.save_data.get("scrip", 0) < cost:
        _flash_status(lbl, "Not Enough Scrip!", "#FF0000"); return
    app.save_data["scrip"] -= cost
    app.save_data["unlocked_task_slots"] = new_level
    engine.save_save_data(app.save_data)
    _flash_status(lbl, "Purchased!", "#00FF00")
    app.after(1000, lambda: refresh_shop_ui(app))
    etw_ui_town.update_town_stats(app)

def _purchase_pool_upgrade(app, cost, new_size, lbl):
    if app.save_data.get("scrip", 0) < cost:
        _flash_status(lbl, "Not Enough Scrip!", "#FF0000"); return
    app.save_data["scrip"] -= cost
    app.save_data["unlocked_task_pool_size"] = new_size
    engine.save_save_data(app.save_data)
    _flash_status(lbl, "Purchased!", "#00FF00")
    app.after(1000, lambda: refresh_shop_ui(app))
    etw_ui_town.update_town_stats(app)

def _purchase_item(app, item, cost_scrip, cost_caps, lbl):
    if cost_scrip > 0 and app.save_data.get("scrip", 0) < cost_scrip:
        _flash_status(lbl, "Not Enough Scrip!", "#FF0000"); return
    if cost_scrip > 0:
        app.save_data["scrip"] -= cost_scrip
        if hasattr(app, 'shop_scrip_label'): app.shop_scrip_label.config(text=f"Scrip: {app.save_data['scrip']}")
    if cost_caps > 0:
        engine._process_game_commands([f"player.removeitem 0000000F {cost_caps}"])
    
    itype = item.get("type")
    if itype == "meta":
        key = item.get("inventory_key")
        if key:
            inv = app.save_data.get("inventory", {})
            inv[key] = inv.get(key, 0) + 1
            app.save_data["inventory"] = inv
    elif itype == "ingame":
        # Add to Game + Local JSON Update?
        # Typically purchase adds item in game. We should ideally update local JSON too.
        # But this is "blind fire". The cleanest way is to assume player has it.
        # For strict tracking, we would update JSON.
        engine._process_game_commands([f"player.additem {item.get('code')} {item.get('qty', 1)}"])
        
        # Local JSON Update for Consistency
        if item.get("code"):
            inventory.update_local_inventory(app.save_data, added_items=[{"code": item["code"], "qty": item.get("qty", 1)}])
            
    _flash_status(lbl, "Purchased!", "#00FF00")
    engine.save_save_data(app.save_data)
    
    app.after(500, lambda: refresh_shop_ui(app))