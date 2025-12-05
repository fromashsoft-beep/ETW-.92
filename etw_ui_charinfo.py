import tkinter as tk
from tkinter import messagebox
import os
import etw_engine as engine
import etw_buffs as buffs
import etw_inventory as inventory # Source of Truth Manager
import etw_stats as stats # Needed for compute_reputation

# ----------------------------------------------------------------------
# UTILITY HELPERS
# ----------------------------------------------------------------------

def _get_stat(baseline, key, default=0):
    """Normalizer for accessing baseline stats, handling case and spacing inconsistencies."""
    # Try exact key first
    if key in baseline: return float(baseline[key])
    # Fallback checks (to handle 'damageresist' vs 'damage resist' or capitalization)
    for k, v in baseline.items():
        if k.lower() == key.lower(): return float(v)
        # Handle cases like "carryweight" vs "carry weight"
        if k.lower().replace(" ", "") == key.lower().replace(" ", ""): return float(v)
    return default

def _format_live_stats(app, char_data):
    """
    Parses the baseline data from character_data.json and formats the live stats display text.
    Returns a formatted string for the live stats label.
    """
    baseline = char_data.get("stats", {})
    stats_text = ""

    if baseline:
        lvl = int(_get_stat(baseline, "level", 1))
        hp = int(_get_stat(baseline, "health", 0))
        ap = int(_get_stat(baseline, "actionpoints", 0))
        cw = int(_get_stat(baseline, "carryweight", 0))
        
        stats_text += f"LEVEL {lvl} | HP: {hp} | AP: {ap} | CW: {cw}\n\n"
        stats_text += "SPECIAL:\n"
        
        special_keys = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
        for s in special_keys:
            val = int(_get_stat(baseline, s, 0))
            stats_text += f" {s[0:3].upper()}: {val}\n"
            
        stats_text += "\nTOP SKILLS:\n"
        skills_found = {}
        # List of keys to exclude from "Top Skills" display
        exclude = set(special_keys + ["health", "actionpoints", "carryweight", "damageresist", "speedmult", "level", "xp", "rads", "fatigue", "karma"])
        
        for k, v in baseline.items():
            if k.lower() in exclude: continue
            try:
                # Normalize key to check for exclusion again just in case of spaces
                normalized_key = k.lower().replace(" ", "")
                if normalized_key in exclude: continue
                
                val = float(v)
                skills_found[k] = val
            except: pass
                
        sorted_skills = sorted(skills_found.items(), key=lambda item: item[1], reverse=True)
        for k, v in sorted_skills[:6]:
            stats_text += f" {k.title()}: {int(v)}\n"
            
        return "--- LIVE STATS ---\n" + stats_text
    
    else:
        # Fallback to initial character theme stats if no scan data is present
        char = app.save_data.get("character", {})
        stats_text = "SPECIAL (BASE):\n"
        for k, v in char.get("stats", {}).items(): 
            stats_text += f" {k[0:3]}: {v}\n"
            
        stats_text += "\nTAG SKILLS (INITIAL):\n " + "\n ".join(char.get("skills", []))
        stats_text += "\n\n(Perform a 'Scan Baseline' in Settings to update)"
        return stats_text

def _format_career_modifiers(app):
    """
    Formats the text for Career Stats and Active Modifiers.
    Returns a formatted string for the career/modifier label.
    """
    # Career Stats
    rep = stats.compute_reputation(app.save_data)
    
    h_txt = f"--- CAREER ---\n"
    h_txt += f"Raids: {app.save_data.get('raids_started', 0)} | Extracted: {app.save_data.get('raids_extracted', 0)} | Died: {app.save_data.get('raids_died', 0)} | SOS: {app.save_data.get('sos_extracts', 0)}\n"
    h_txt += f"Contracts Completed: {app.save_data.get('total_completed_tasks', 0)}\n"
    h_txt += f"Emergency Contracts Completed: {app.save_data.get('emergency_completed', 0)}\n"
    h_txt += f"Tasks Failed: {app.save_data.get('tasks_failed', 0)} (Emergency Failed: {app.save_data.get('emergency_tasks_failed', 0)})\n"
    h_txt += f"[E: {app.save_data.get('easy_completed', 0)} | M: {app.save_data.get('medium_completed', 0)} | H: {app.save_data.get('hard_completed', 0)}]\n\n"
    
    # Modifiers
    mods = buffs.get_player_modifiers(app.save_data)
    base_fortune = app.save_data.get("fortune", 0.0)
    total_xp = buffs.calculate_cumulative_multiplier(app.save_data, "xp")
    total_caps = buffs.calculate_cumulative_multiplier(app.save_data, "caps")
    total_scrip = buffs.calculate_cumulative_multiplier(app.save_data, "scrip")
    
    h_txt += f"--- ACTIVE MODIFIERS ---\n"
    h_txt += f"Reputation: {rep:.1f}\n"
    h_txt += f"Fortune: {base_fortune:.1f} (Effective: {mods['effective_fortune']:.1f})\n"
    h_txt += f"XP Bonus: {int((total_xp-1.0)*100)}%\n"
    h_txt += f"Caps Bonus: {int((total_caps-1.0)*100)}%\n"
    h_txt += f"Scrip Bonus: {int((total_scrip-1.0)*100)}%\n"
    h_txt += f"Loot Count Bonus: +{mods['loot_count_bonus']}"
    
    return h_txt


# ----------------------------------------------------------------------
# BUILDERS
# ----------------------------------------------------------------------

def build_character_info_screen(app, frame):
    """
    Constructs the Character Sheet UI.
    """
    # 1. Header
    tk.Label(frame, text="Character Sheet", fg="#00FF00", bg="#111111", font=("Courier", 24, "bold")).pack(pady=5)
    
    # 2. Navigation
    nav = tk.Frame(frame, bg="#111111")
    nav.pack(fill="x", pady=5, padx=20)
    
    tk.Button(nav, text="Return to Town", command=app.show_town_screen, bg="#003300", fg="#00FF00", font=("Courier", 12, "bold")).pack(side="left")
    
    app.info_scrip_lbl = tk.Label(nav, text="", fg="#FFD700", bg="#111111", font=("Courier", 12, "bold"))
    app.info_scrip_lbl.pack(side="right")
    
    # 3. Theme Details
    details = tk.Frame(frame, bg="#111111", bd=2, relief="groove")
    details.pack(fill="both", expand=True, padx=20, pady=10)
    
    app.info_theme_name_lbl = tk.Label(details, text="", fg="#FFFFFF", bg="#111111", font=("Courier", 18, "bold"))
    app.info_theme_name_lbl.pack(pady=5)
    
    app.info_desc_lbl = tk.Label(details, text="", fg="#CCCCCC", bg="#111111", font=("Courier", 12), justify="center")
    app.info_desc_lbl.pack(pady=5, padx=10)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.info_desc_lbl)
        
    # 4. Live Stats (Scanned)
    stats_frame = tk.Frame(details, bg="#111111")
    stats_frame.pack(pady=10, fill="x", padx=20)
    
    app.info_stats_lbl = tk.Label(stats_frame, text="", fg="#00FFFF", bg="#111111", font=("Courier", 11), justify="left")
    app.info_stats_lbl.pack(side="left", anchor="n")
    
    # 5. Strategy Hint
    bottom_info = tk.Frame(details, bg="#111111")
    bottom_info.pack(side="top", fill="x", padx=20, pady=10)
    
    tk.Label(bottom_info, text="Strategy:", fg="#FFFF00", bg="#111111", font=("Courier", 11, "bold")).pack(anchor="w")
    
    app.info_strategy_lbl = tk.Label(bottom_info, text="", fg="#FFFFE0", bg="#111111", font=("Courier", 10), justify="center")
    app.info_strategy_lbl.pack(pady=5)
    if hasattr(app, 'register_wrappable'):
        app.register_wrappable(app.info_strategy_lbl)
        
    # 6. Career Stats & Modifiers
    tk.Label(frame, text="Career & Modifiers", fg="#FFD700", bg="#111111", font=("Courier", 14, "bold")).pack(pady=5)
    
    app.history_stats_lbl = tk.Label(frame, text="", fg="#AAAAAA", bg="#111111", font=("Courier", 12), justify="center")
    app.history_stats_lbl.pack(pady=5)
    
    # 7. Bottom Controls
    btn_row = tk.Frame(frame, bg="#111111")
    btn_row.pack(side="bottom", pady=20, fill="x")
    
    right_btns = tk.Frame(btn_row, bg="#111111")
    right_btns.pack(side="right", padx=20)
    
    tk.Button(right_btns, text="Settings", command=app.show_settings_screen, bg="#333333", fg="#FFFFFF").pack(side="left", padx=5)
    tk.Button(right_btns, text="RESET DATA", command=lambda: _reset_data_gui(app), bg="#550000", fg="#FFFFFF").pack(side="left", padx=5)


# ----------------------------------------------------------------------
# UPDATERS
# ----------------------------------------------------------------------

def refresh_character_info_ui(app):
    """
    Populates all labels with current save data.
    (Monolithic function broken down into helper functions)
    """
    char = app.save_data.get("character")
    if not char:
        app.info_theme_name_lbl.config(text="No character data.")
        return
    
    # Basic Info
    app.info_scrip_lbl.config(text=f"Scrip: {app.save_data.get('scrip', 0)}")
    app.info_theme_name_lbl.config(text=char['name'])
    app.info_desc_lbl.config(text=char['description'])
    app.info_strategy_lbl.config(text=char.get("level_up", "No strategy provided."))
    
    # Live Stats (from Source of Truth)
    game_path = app.save_data.get("game_install_path", "")
    char_data = inventory.get_character_data(game_path)
    
    # 1. Format Live Stats
    live_stats_text = _format_live_stats(app, char_data)
    app.info_stats_lbl.config(text=live_stats_text)
    
    # 2. Format Career & Modifiers
    career_mods_text = _format_career_modifiers(app)
    app.history_stats_lbl.config(text=career_mods_text)


# ----------------------------------------------------------------------
# ACTIONS
# ----------------------------------------------------------------------

def _reset_data_gui(app):
    if not messagebox.askyesno("Confirm Reset", "Are you sure you want to delete your save and start over?"): 
        return
        
    path = app.save_data.get("game_install_path")
    
    if os.path.exists(engine.PATHS["save_data"]): 
        try:
            os.remove(engine.PATHS["save_data"])
        except Exception as e:
            print(f"Error deleting save: {e}")
            
    # ALSO DELETE CHARACTER DATA
    if os.path.exists(inventory.CHAR_DATA_FILENAME):
        try: os.remove(inventory.CHAR_DATA_FILENAME)
        except: pass
            
    app.save_data = engine.load_save_data()
    app.save_data["game_install_path"] = path
    engine.save_save_data(app.save_data)
    
    app.current_character = None
    app.show_splash()