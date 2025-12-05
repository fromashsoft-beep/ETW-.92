import tkinter as tk
import random
import os

# Foundation
import etw_config as config
import etw_io as io

# Sub-Systems
import etw_engine as engine
import etw_bridge as bridge
import etw_inventory as inventory # Required for filename constant

# ----------------------------------------------------------------------
# STATE
# ----------------------------------------------------------------------
# Local state for the UI session
_GEN_STATE = {
    "options": [],          # The 3 random themes
    "selected_slot": 0,     # Index of selected random option
    "picker_index": 0,      # Index in full list for manual picker
    "themes_cache": []      # Full list of themes
}

# ----------------------------------------------------------------------
# SCREEN 1: RANDOM SELECTION (The "Personality Test" Vibe)
# ----------------------------------------------------------------------

def build_character_gen_screen(app, frame):
    """
    Constructs the Quick Select screen.
    """
    tk.Label(frame, text="Select your Character", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=10)
    
    # 1. Slot Buttons
    btn_frame = tk.Frame(frame, bg="#111111")
    btn_frame.pack(pady=10)
    
    app.char_btn_1 = tk.Button(btn_frame, text="1", command=lambda: _select_char_slot(app, 0), font=("Courier", 14, "bold"), width=5, bg="#222222", fg="#FFFFFF")
    app.char_btn_1.pack(side="left", padx=10)
    
    app.char_btn_2 = tk.Button(btn_frame, text="2", command=lambda: _select_char_slot(app, 1), font=("Courier", 14, "bold"), width=5, bg="#222222", fg="#FFFFFF")
    app.char_btn_2.pack(side="left", padx=10)
    
    app.char_btn_3 = tk.Button(btn_frame, text="3", command=lambda: _select_char_slot(app, 2), font=("Courier", 14, "bold"), width=5, bg="#222222", fg="#FFFFFF")
    app.char_btn_3.pack(side="left", padx=10)
    
    # 2. Details Panel
    details = tk.Frame(frame, bg="#111111", bd=2, relief="groove")
    details.pack(fill="both", expand=True, padx=20, pady=10)
    
    app.char_theme_name_lbl = tk.Label(details, text="", fg="#FFFFFF", bg="#111111", font=("Courier", 18, "bold"))
    app.char_theme_name_lbl.pack(pady=5)
    
    app.char_desc_lbl = tk.Label(details, text="", fg="#CCCCCC", bg="#111111", font=("Courier", 12), justify="center")
    app.char_desc_lbl.pack(pady=5, padx=10)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.char_desc_lbl)
        
    stats_frame = tk.Frame(details, bg="#111111")
    stats_frame.pack(pady=10, fill="x", padx=20)
    
    app.char_stats_lbl = tk.Label(stats_frame, text="", fg="#00FFFF", bg="#111111", font=("Courier", 11), justify="left")
    app.char_stats_lbl.pack(side="left", anchor="n")
    
    bottom_info = tk.Frame(details, bg="#111111")
    bottom_info.pack(side="top", fill="x", padx=20, pady=10)
    
    tk.Label(bottom_info, text="Starting Gear:", fg="#00FF00", bg="#111111", font=("Courier", 11, "bold")).pack(anchor="w")
    app.char_loadout_lbl = tk.Label(bottom_info, text="", fg="#CCFFCC", bg="#111111", font=("Courier", 9), justify="left")
    app.char_loadout_lbl.pack(anchor="w", pady=(0, 10))
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.char_loadout_lbl)
        
    tk.Label(bottom_info, text="Strategy:", fg="#FFFF00", bg="#111111", font=("Courier", 11, "bold")).pack(anchor="w")
    app.char_strategy_lbl = tk.Label(bottom_info, text="", fg="#FFFFE0", bg="#111111", font=("Courier", 10), justify="center")
    app.char_strategy_lbl.pack(pady=5)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.char_strategy_lbl)
    
    # 3. Actions
    tk.Button(frame, text="CONFIRM SELECTION", command=lambda: _confirm_selection(app), bg="#003300", fg="#00FF00", font=("Courier", 16, "bold")).pack(pady=10)
    tk.Button(frame, text="Let me choose...", command=lambda: _switch_to_picker(app), bg="#222222", fg="#AAAAAA", font=("Courier", 10)).pack(pady=5)

# ----------------------------------------------------------------------
# SCREEN 2: MANUAL PICKER (Cycling through all)
# ----------------------------------------------------------------------

def build_character_picker_screen(app, frame):
    """
    Constructs the Manual Picker screen.
    """
    tk.Label(frame, text="Manual Selection", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=10)
    
    # 1. Navigation
    nav = tk.Frame(frame, bg="#111111")
    nav.pack(pady=10)
    
    tk.Button(nav, text="< PREV", command=lambda: _cycle_picker(app, -1), bg="#333333", fg="#FFFFFF").pack(side="left", padx=20)
    app.picker_count_lbl = tk.Label(nav, text="1/10", fg="#FFFFFF", bg="#111111", font=("Courier", 12))
    app.picker_count_lbl.pack(side="left", padx=20)
    tk.Button(nav, text="NEXT >", command=lambda: _cycle_picker(app, 1), bg="#333333", fg="#FFFFFF").pack(side="left", padx=20)
    
    # 2. Details Panel (Reused Layout)
    details = tk.Frame(frame, bg="#111111", bd=2, relief="groove")
    details.pack(fill="both", expand=True, padx=20, pady=10)
    
    app.picker_name_lbl = tk.Label(details, text="", fg="#FFFFFF", bg="#111111", font=("Courier", 18, "bold"))
    app.picker_name_lbl.pack(pady=5)
    
    app.picker_desc_lbl = tk.Label(details, text="", fg="#CCCCCC", bg="#111111", font=("Courier", 12), justify="center")
    app.picker_desc_lbl.pack(pady=5, padx=10)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.picker_desc_lbl)
        
    stats_frame = tk.Frame(details, bg="#111111")
    stats_frame.pack(pady=10, fill="x", padx=20)
    app.picker_stats_lbl = tk.Label(stats_frame, text="", fg="#00FFFF", bg="#111111", font=("Courier", 11), justify="left")
    app.picker_stats_lbl.pack(side="left", anchor="n")
    
    bottom_info = tk.Frame(details, bg="#111111")
    bottom_info.pack(side="top", fill="x", padx=20, pady=10)
    
    tk.Label(bottom_info, text="Starting Gear:", fg="#00FF00", bg="#111111", font=("Courier", 11, "bold")).pack(anchor="w")
    app.picker_loadout_lbl = tk.Label(bottom_info, text="", fg="#CCFFCC", bg="#111111", font=("Courier", 9), justify="left")
    app.picker_loadout_lbl.pack(anchor="w", pady=(0, 10))
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.picker_loadout_lbl)
        
    tk.Label(bottom_info, text="Strategy:", fg="#FFFF00", bg="#111111", font=("Courier", 11, "bold")).pack(anchor="w")
    app.picker_strategy_lbl = tk.Label(bottom_info, text="", fg="#FFFFE0", bg="#111111", font=("Courier", 10), justify="center")
    app.picker_strategy_lbl.pack(pady=5)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.picker_strategy_lbl)
        
    # 3. Actions
    ctrl = tk.Frame(frame, bg="#111111")
    ctrl.pack(pady=20)
    tk.Button(ctrl, text="Back", command=lambda: app.lift_screen("character_gen"), bg="#330000", fg="#FF0000", font=("Courier", 12)).pack(side="left", padx=20)
    tk.Button(ctrl, text="CONFIRM THIS CHARACTER", command=lambda: _confirm_picker_selection(app), bg="#003300", fg="#00FF00", font=("Courier", 14, "bold")).pack(side="left", padx=20)

# ----------------------------------------------------------------------
# LOGIC & NAVIGATION
# ----------------------------------------------------------------------

def start_character_gen(app):
    """
    Called by App to initialize the flow.
    Generates 3 random options if needed.
    """
    # Always reload themes to be safe
    _GEN_STATE["themes_cache"] = io.load_json(config.PATHS["character_themes"], [])
        
    # Always reroll options on start for freshness
    if _GEN_STATE["themes_cache"]:
        themes_copy = _GEN_STATE["themes_cache"][:]
        random.shuffle(themes_copy)
        _GEN_STATE["options"] = themes_copy[:3]
        
    _GEN_STATE["selected_slot"] = 0
    _refresh_gen_ui(app)
    app.lift_screen("character_gen")

def _select_char_slot(app, slot_idx):
    _GEN_STATE["selected_slot"] = slot_idx
    
    # Visual update for buttons
    btns = [app.char_btn_1, app.char_btn_2, app.char_btn_3]
    for i, btn in enumerate(btns):
        if i == slot_idx: 
            btn.config(bg="#004400", fg="#00FF00")
        else: 
            btn.config(bg="#222222", fg="#FFFFFF")
            
    _refresh_gen_ui(app)

def _refresh_gen_ui(app):
    if not _GEN_STATE["options"]: return
    
    theme = _GEN_STATE["options"][_GEN_STATE["selected_slot"]]
    app.char_theme_name_lbl.config(text=theme["name"])
    app.char_desc_lbl.config(text=theme["description"])
    app.char_strategy_lbl.config(text=theme.get("level_up", "No strategy provided."))
    
    _update_stats_display(app.char_stats_lbl, theme)
    _update_loadout_display(app.char_loadout_lbl, theme)

def _switch_to_picker(app):
    _GEN_STATE["picker_index"] = 0
    _refresh_picker_ui(app)
    app.lift_screen("character_picker")

def _cycle_picker(app, direction):
    themes = _GEN_STATE["themes_cache"]
    if not themes: return
    
    idx = _GEN_STATE["picker_index"] + direction
    if idx < 0: idx = len(themes) - 1
    if idx >= len(themes): idx = 0
    
    _GEN_STATE["picker_index"] = idx
    _refresh_picker_ui(app)

def _refresh_picker_ui(app):
    themes = _GEN_STATE["themes_cache"]
    if not themes: return
    
    idx = _GEN_STATE["picker_index"]
    theme = themes[idx]
    
    app.picker_count_lbl.config(text=f"{idx + 1}/{len(themes)}")
    app.picker_name_lbl.config(text=theme["name"])
    app.picker_desc_lbl.config(text=theme["description"])
    app.picker_strategy_lbl.config(text=theme.get("level_up", "No strategy provided."))
    
    _update_stats_display(app.picker_stats_lbl, theme)
    _update_loadout_display(app.picker_loadout_lbl, theme)

# ----------------------------------------------------------------------
# FINALIZATION
# ----------------------------------------------------------------------

def _confirm_selection(app):
    if not _GEN_STATE["options"]: return
    theme = _GEN_STATE["options"][_GEN_STATE["selected_slot"]]
    _finalize_character_creation(app, theme)

def _confirm_picker_selection(app):
    themes = _GEN_STATE["themes_cache"]
    if not themes: return
    theme = themes[_GEN_STATE["picker_index"]]
    _finalize_character_creation(app, theme)

def _finalize_character_creation(app, theme):
    """
    Saves the character, grants starting items, and moves to Town.
    NOW CLEARS PREVIOUS CHARACTER TRACKING DATA.
    """
    # 1. Clear previous Source of Truth file if it exists
    char_data_path = os.path.join(os.getcwd(), inventory.CHAR_DATA_FILENAME)
    if os.path.exists(char_data_path):
        try:
            os.remove(char_data_path)
            print("Previous character data cleared.")
        except Exception as e:
            print(f"Error clearing character data: {e}")

    # 2. Reload Save Data (Safe refresh)
    app.save_data = io.load_json(config.PATHS["save_data"], app.save_data) 
    
    # 3. Apply New Character Theme
    app.save_data["character"] = theme
    app.save_data["scrip"] = 0
    
    # 4. Grant Loadout
    loadouts = io.load_json(config.PATHS["starter_loadouts"], {})
    spec = theme.get("specialty", "")
    items = loadouts.get(spec, [])
    
    cmds = []
    for item in items: 
        cmds.append(f"player.additem {item['code']} {item['quantity']}")
        
    game_path = app.save_data.get("game_install_path", "")
    if game_path:
        bridge.process_game_commands(game_path, cmds)
        
    # 5. Final Save & Transition
    io.save_json(config.PATHS["save_data"], app.save_data)
    app.current_character = theme
    app.show_town_screen()

# ----------------------------------------------------------------------
# DISPLAY HELPERS
# ----------------------------------------------------------------------

def _update_stats_display(label, theme):
    stats_text = "SPECIAL:\n"
    for k, v in theme["stats"].items(): 
        stats_text += f" {k[0:3]}: {v}\n"
        
    stats_text += "\nTAG SKILLS:\n " + "\n ".join(theme["skills"])
    label.config(text=stats_text)

def _update_loadout_display(label, theme):
    loadouts = io.load_json(config.PATHS["starter_loadouts"], {})
    spec = theme.get("specialty", "")
    items = loadouts.get(spec, [])
    
    items_txt = "\n".join([f"- {i['name']} (x{i['quantity']})" for i in items]) if items else "- None"
    label.config(text=items_txt)