import tkinter as tk
import os
import etw_engine as engine
import etw_inventory as inventory 
import etw_config as config
import etw_io as io

# ----------------------------------------------------------------------
# INVENTORY UI MODULE (Restored Insurance Logic)
# ----------------------------------------------------------------------

def build_inventory_screen(app, frame):
    # 1. Header
    tk.Label(frame, text="Inventory", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=5)

    # 2. Navigation
    nav_frame = tk.Frame(frame, bg="#111111")
    nav_frame.pack(fill="x", pady=5, padx=20)
    tk.Button(nav_frame, text="Return to Town", command=app.show_town_screen, bg="#003300", fg="#00FF00", font=("Courier", 12, "bold")).pack(side="left")
    
    app.inventory_scrip_label = tk.Label(nav_frame, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.inventory_scrip_label.pack(side="right")

    # 3. Feedback
    app.inventory_feedback_label = tk.Label(frame, text="", fg="#00FF00", bg="#111111", font=("Courier", 12, "bold"))
    app.inventory_feedback_label.pack(pady=5)
    
    # 4. Actions
    action_frame = tk.Frame(frame, bg="#111111")
    action_frame.pack(fill="x", padx=20)
    tk.Button(action_frame, text="STORED INVENTORY (JSON)", command=lambda: _show_stored_inventory_view(app), bg="#333333", fg="#AAAAAA", font=("Courier", 10)).pack(side="left")
    tk.Button(action_frame, text="VIEW INTEL DOSSIER", command=lambda: _show_dossier_view(app), bg="#003333", fg="#00FFFF", font=("Courier", 10, "bold")).pack(side="right")
    
    # 5. Content
    app.inventory_content_frame = tk.Frame(frame, bg="#111111")
    app.inventory_content_frame.pack(fill="both", expand=True, padx=20, pady=10)

def refresh_inventory_ui(app):
    for w in app.inventory_content_frame.winfo_children(): w.destroy()
    
    inv = app.save_data.get("inventory", {})
    current_scrip = app.save_data.get('scrip', 0)
    if hasattr(app, 'inventory_scrip_label'):
        app.inventory_scrip_label.config(text=f"Scrip: {current_scrip}")
    
    # Consumables
    tk.Label(app.inventory_content_frame, text="--- Consumables ---", fg="#00FFFF", bg="#111111", font=("Courier", 10, "bold")).pack(pady=(0, 5))
    
    qty_lunch = inv.get("lunchbox", 0)
    _build_item_row(app, "Lunchbox", qty_lunch, "Grant random buff for next raid.", lambda: _handle_use_lunchbox(app) if qty_lunch > 0 else None, (qty_lunch > 0))
    
    qty_flare = inv.get("sos_flare", 0)
    _build_item_row(app, "SoS Flare", qty_flare, "Use during Raid for emergency extraction.", None, False) 
    
    qty_reroll = inv.get("task_reroll", 0)
    _build_item_row(app, "Contract Reroller", qty_reroll, "Reroll active contracts at the Board.", None, False) 

    # History
    tk.Label(app.inventory_content_frame, text="--- Recent Acquisitions ---", fg="#00FFFF", bg="#111111", font=("Courier", 10, "bold")).pack(pady=(20, 5))
    history = app.save_data.get("reward_history", [])
    if not history:
        tk.Label(app.inventory_content_frame, text="No recent history.", fg="#555555", bg="#111111", font=("Courier", 10)).pack()
    else:
        for entry in reversed(history[-10:]):
            _build_history_row(app, entry)

def _build_item_row(app, name, qty, desc, use_cmd, can_use):
    bg = "#222222"
    f = tk.Frame(app.inventory_content_frame, bg=bg, bd=1, relief="ridge")
    f.pack(fill="x", pady=5)
    
    info = tk.Frame(f, bg=bg)
    info.pack(side="left", fill="x", expand=True, padx=10, pady=5)
    tk.Label(info, text=f"{name} (x{qty})", fg="#FFFFFF", bg=bg, font=("Courier", 12, "bold")).pack(anchor="w")
    tk.Label(info, text=desc, fg="#AAAAAA", bg=bg, font=("Courier", 10)).pack(anchor="w")
    
    if use_cmd:
        state = "normal" if can_use else "disabled"
        btn_bg = "#004400" if can_use else "#333333"
        tk.Button(f, text="USE", command=use_cmd, state=state, bg=btn_bg, fg="#00FF00").pack(side="right", padx=10)
    elif name == "SoS Flare":
        tk.Label(f, text="[Use in Raid]", fg="#555555", bg=bg, font=("Courier", 10)).pack(side="right", padx=10)

def _build_history_row(app, entry):
    f = tk.Frame(app.inventory_content_frame, bg="#1a1a1a", bd=0)
    f.pack(fill="x", pady=1)
    
    source = entry.get("source", "Unknown")
    time_str = entry.get("time", "")
    tk.Label(f, text=f"[{source}] {time_str}", fg="#888888", bg="#1a1a1a", font=("Courier", 8)).pack(anchor="w", padx=5)
    
    rewards = []
    if entry.get("xp"): rewards.append(f"{entry['xp']} XP")
    if entry.get("caps"): rewards.append(f"{entry['caps']} Caps")
    if entry.get("scrip"): rewards.append(f"{entry['scrip']} Scrip")
    
    items = entry.get("items", [])
    item_str = ", ".join([f"{i.get('name')} (x{i.get('qty',1)})" for i in items])
    
    final_text = ", ".join(rewards)
    if items: final_text += " | " + item_str
    if not final_text: final_text = "No rewards."
    
    tk.Label(f, text=f" > {final_text}", fg="#CCCCCC", bg="#1a1a1a", font=("Courier", 9), wraplength=app.current_wrap_width-40, justify="left").pack(anchor="w", padx=15)

def _show_stored_inventory_view(app):
    for w in app.inventory_content_frame.winfo_children(): w.destroy()
    
    tk.Label(app.inventory_content_frame, text="Stored Inventory (Source of Truth)", fg="#FFAA00", bg="#111111", font=("Courier", 14, "bold")).pack(pady=10)
    tk.Label(app.inventory_content_frame, text="Select items to INSURE (persist after death).", fg="#AAAAAA", bg="#111111", font=("Courier", 10)).pack(pady=2)
    
    container = tk.Frame(app.inventory_content_frame, bg="#111111", bd=2, relief="sunken")
    container.pack(fill="both", expand=True, padx=10, pady=5)
    
    canvas = tk.Canvas(container, bg="#000000", highlightthickness=0)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg="#000000")
    
    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    game_path = app.save_data.get("game_install_path", "")
    char_data = inventory.get_character_data(game_path)
    inv_list = char_data.get("inventory", [])
    insured_items = app.save_data.get("insured_items", [])
    
    if not inv_list:
        tk.Label(scroll_frame, text="No items found. Run a scan in Settings.", fg="#555555", bg="#000000", font=("Courier", 10)).pack(pady=20)
    else:
        inv_list.sort(key=lambda x: x.get("name", "Unknown"))
        for item in inv_list:
            code = item.get("code")
            name = item.get("name", "Unknown")
            qty = item.get("qty", 1)
            
            row = tk.Frame(scroll_frame, bg="#222222", bd=1, relief="solid")
            row.pack(fill="x", pady=1, padx=2)
            
            is_safe = code in insured_items
            name_col = "#FFFFFF" if is_safe else "#AAAAAA"
            
            tk.Label(row, text=f"{name} (x{qty})", fg=name_col, bg="#222222", font=("Courier", 10)).pack(side="left", padx=5)
            
            # THE CRITICAL TOGGLE BUTTON
            btn_txt = "SAFE" if is_safe else "UNSAFE"
            btn_bg = "#004400" if is_safe else "#333333"
            btn_fg = "#00FF00" if is_safe else "#555555"
            
            tk.Button(row, text=btn_txt, command=lambda c=code: _toggle_safe_status(app, c), 
                      bg=btn_bg, fg=btn_fg, font=("Courier", 8, "bold"), width=8).pack(side="right", padx=5, pady=2)

    tk.Button(app.inventory_content_frame, text="Close", command=lambda: refresh_inventory_ui(app), bg="#333333", fg="#FFFFFF").pack(pady=10)

def _toggle_safe_status(app, item_code):
    if "insured_items" not in app.save_data: app.save_data["insured_items"] = []
    
    if item_code in app.save_data["insured_items"]:
        app.save_data["insured_items"].remove(item_code)
    else:
        app.save_data["insured_items"].append(item_code)
        
    io.save_json(config.PATHS["save_data"], app.save_data)
    _show_stored_inventory_view(app)

def _show_dossier_view(app):
    for w in app.inventory_content_frame.winfo_children(): w.destroy()
    tk.Label(app.inventory_content_frame, text="INTEL DOSSIER", fg="#00FFFF", bg="#111111", font=("Courier", 16, "bold")).pack(pady=10)
    unlocked = app.save_data.get("unlocked_intel", [])
    if not unlocked:
        tk.Label(app.inventory_content_frame, text="No intel acquired.", fg="#555555", bg="#111111", font=("Courier", 12)).pack(pady=20)
    else:
        intel_db = io.load_json(config.PATHS["content_intel"])
        all_intel = intel_db.get("raid_intel", []) + intel_db.get("general_rumors", [])
        for intel_id in unlocked:
            data = next((i for i in all_intel if i["id"] == intel_id), None)
            if data:
                row = tk.Frame(app.inventory_content_frame, bg="#222222", bd=1, relief="ridge")
                row.pack(fill="x", pady=5)
                tk.Label(row, text=data["title"], fg="#FFFF00", bg="#222222", font=("Courier", 11, "bold")).pack(anchor="w", padx=5)
                tk.Label(row, text=data["text"], fg="#CCCCCC", bg="#222222", font=("Courier", 9), wraplength=450, justify="left").pack(anchor="w", padx=10, pady=2)
    tk.Button(app.inventory_content_frame, text="Close Dossier", command=lambda: refresh_inventory_ui(app), bg="#333333", fg="#FFFFFF").pack(pady=20)

def _handle_use_lunchbox(app):
    res = engine.use_lunchbox(app.save_data)
    if res["success"]:
        app.show_temporary_text(app.inventory_feedback_label, f"Opened: {res['buff_name']}", "#FFFF00")
    else:
        app.show_temporary_text(app.inventory_feedback_label, res["message"], "#FF0000")
    refresh_inventory_ui(app)