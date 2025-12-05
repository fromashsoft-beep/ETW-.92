import tkinter as tk
from tkinter import messagebox, filedialog 
import sys
import os
import time
import datetime
import traceback
import atexit 
import ctypes
import collections 
import random 

# Foundation Modules
import etw_config as config
import etw_io as io

# Core Systems
import etw_engine as engine
import etw_raid as raid
import etw_ambush as ambush 
import etw_hotkeys
import etw_bridge as bridge
import etw_game_timer as game_timer
import etw_inventory as inventory 
import etw_loot 
import etw_buff_manager as buff_manager
import etw_dialogue as dialogue 

# UI Modules
import etw_ui_town
import etw_ui_game
import etw_ui_chargen
import etw_ui_charinfo
import etw_ui_settings
import etw_ui_quests
import etw_ui_shop
import etw_ui_inventory
import etw_ui_hideout
import etw_ui_bar
import etw_ui_raid_transition

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
VERSION = "v.14.52 (Non-Blocking I/O)"
AHK_WAIT_MS = int(bridge.AHK_EXECUTION_TIME * 1000)
ERROR_LOG_FILE = "error_log.txt"

# REFACTORED: Loaded from JSON
INTRO_TEXT = [] 

class EscapeTheWastelandApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # --- 1. Enhanced Error Tracking Setup ---
        self.action_history = collections.deque(maxlen=15)
        self._setup_logging_hooks()
        
        try:
            if os.name == 'nt':
                ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)
        except Exception as e:
            pass
        
        self.title(f"Escape the Wasteland - {VERSION}")
        self.configure(bg="#111111")
        self.geometry("950x950") 
        self.resizable(True, True)
        
        self.current_wrap_width = 860
        self._resize_job = None 
        self.wrappable_labels = []
        self.screens = {}
        
        # --- 2. Global Event Listeners (Breadcrumbs) ---
        self.bind_all("<Button-1>", self._track_interaction)
        self.bind_all("<KeyRelease>", self._track_interaction)
        
        # Load Static Content
        self.main_quests = engine.load_main_quests()
        self.side_quests = engine.load_side_quests()
        self.shop_items = engine.load_shop_items()
        
        # Load Intro Text
        global INTRO_TEXT
        INTRO_TEXT = dialogue.get_intro_text()
        
        etw_loot.get_loot_pool_cached() 
        
        self.save_data = engine.load_save_data()
        self.current_character = self.save_data.get("character")
        self.hotkey_manager = etw_hotkeys.GlobalHotkeyManager(self, self)
        
        self.quest_display_page = 0
        self.quests_per_page = 3
        self.pending_raid_context = None 
        
        self.intro_step = 0
        self.intro_active = False
        self.intro_skipped = False
        
        self._log_startup_version()
        self.create_screens()
        self.build_all_screens()
        self.bind("<Configure>", self.on_window_resize)
        
        # Always show splash first.
        self.show_splash()
            
        self.update_raid_timer()
            
        atexit.register(self.hotkey_manager.cleanup)

    # ------------------------------------------------------------------
    # ERROR LOGGING SYSTEM
    # ------------------------------------------------------------------
    def _setup_logging_hooks(self):
        # Hook 1: General Python Exceptions
        sys.excepthook = self.handle_fatal_error
        
        # Hook 2: Tkinter Callback Exceptions (Button clicks, timers)
        self.report_callback_exception = self.handle_fatal_error
        
        # Init Log File
        try:
            with open(ERROR_LOG_FILE, "w") as f:
                f.write(f"--- Session Started: {datetime.datetime.now()} ---\n")
                f.write(f"Version: {VERSION}\n")
        except: pass

    def _track_interaction(self, event):
        """
        Records the last 15 user interactions to contextually locate errors.
        """
        try:
            widget = event.widget
            w_desc = str(widget)
            details = ""
            
            # Try to get text from buttons/labels
            if hasattr(widget, "cget"):
                try:
                    text = widget.cget("text")
                    if text: details = f" [Text: '{text[:30]}...']"
                except: pass
                
            msg = f"{event.type} on {w_desc}{details}"
            self.action_history.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")
        except: pass

    def handle_fatal_error(self, exc_type, exc_value, exc_traceback):
        """
        Centralized error handler. Dumps context + stack trace to log.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(ERROR_LOG_FILE, "a") as f:
                f.write("\n" + "="*60 + "\n")
                f.write(f"CRITICAL ERROR at {timestamp}\n")
                f.write("="*60 + "\n\n")
                
                f.write("--- USER ACTION HISTORY (Last 15) ---\n")
                for action in self.action_history:
                    f.write(f"{action}\n")
                f.write("-" * 37 + "\n\n")
                
                f.write("--- TRACEBACK ---\n")
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
                f.write("\n")
                
            print(f"\n!!! ERROR LOGGED TO {ERROR_LOG_FILE} !!!\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback) # Still show in console
            
        except Exception as e:
            print(f"FAILED TO WRITE ERROR LOG: {e}")
            traceback.print_exception(exc_type, exc_value, exc_traceback)

    # ------------------------------------------------------------------
    # CORE APP LOGIC
    # ------------------------------------------------------------------

    def _log_startup_version(self):
        log_path = config.PATHS["version_log"]
        try:
            if not os.path.exists(log_path):
                with open(log_path, "w") as f: f.write("")
            with open(log_path, "a") as f: 
                f.write(f"[{datetime.datetime.now()}] Started version: {VERSION}\n")
        except: pass

    def _prompt_resume_raid(self):
        if messagebox.askyesno("Resume Raid?", "An active raid session was detected.\nDo you want to resume your current raid?"):
            self.show_game_screen()
        else:
            # Abandon Logic
            self.save_data["raid_active"] = False
            self.save_data["raid_paused"] = False
            engine.save_save_data(self.save_data)
            self.show_town_screen()
            self._check_startup_buff_state()

    def _check_startup_buff_state(self):
        """
        Checks if buffs are active but potentially desynced from game state.
        This runs when entering Town (startup or return).
        """
        if not self.save_data.get("companion_buffs", False): return
        
        # If the app thinks buffs are active (e.g. crash during raid, or residual state)
        if self.save_data.get("buffs_active", False):
            # Prompt user
            msg = "The app detects active Companion Buffs from a previous session.\n\n"
            msg += "If you loaded an old save file WITHOUT buffs, click YES to reset app tracking to match.\n"
            msg += "If your game save HAS buffs, click NO to keep them."
            
            if messagebox.askyesno("Sync Check", msg):
                # Reset App State (assume game has no buffs)
                self.save_data["buffs_active"] = False
                self.save_data["current_bonuses"] = {}
                engine.save_save_data(self.save_data)
            else:
                # Keep State (assume game has buffs).
                # We might want to remove them if we are now in town.
                if self.get_active_screen_name() == "town":
                     buff_manager.remove_companion_buffs(self.save_data)

    def create_screens(self):
        screen_names = [
            "splash", "intro", "character_gen", "character_picker", "character_info", 
            "town", "game", "quest_log", "settings",
            "shop", "inventory", "hideout", "bar",
            "departing", "raid_end"
        ]
        for name in screen_names:
            f = tk.Frame(self, bg="#111111")
            f.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.screens[name] = f

    def get_screen_frame(self, name): 
        return self.screens[name]
    
    def lift_screen(self, name): 
        self.screens[name].lift()
        self.update_idletasks()
        # Log screen transition
        self.action_history.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Screen Transition -> {name}")

    def get_active_screen_name(self):
        for name, frame in self.screens.items():
            if frame.winfo_ismapped(): return name
        return None

    def build_all_screens(self):
        self._build_splash()
        self._build_intro_screen()
        
        etw_ui_chargen.build_character_gen_screen(self, self.get_screen_frame("character_gen"))
        etw_ui_chargen.build_character_picker_screen(self, self.get_screen_frame("character_picker"))
        etw_ui_charinfo.build_character_info_screen(self, self.get_screen_frame("character_info"))
        etw_ui_settings.build_settings_screen(self, self.get_screen_frame("settings"))
        etw_ui_town.build_town_screen(self, self.get_screen_frame("town"))
        etw_ui_game.build_game_screen(self, self.get_screen_frame("game"))
        etw_ui_quests.build_quest_log_screen(self, self.get_screen_frame("quest_log"))
        etw_ui_shop.build_shop_screen(self, self.get_screen_frame("shop"))
        etw_ui_inventory.build_inventory_screen(self, self.get_screen_frame("inventory"))
        etw_ui_hideout.build_hideout_screen(self, self.get_screen_frame("hideout"))
        etw_ui_bar.build_bar_screen(self, self.get_screen_frame("bar"))
        etw_ui_raid_transition.build_departing_screen(self, self.get_screen_frame("departing"))
        etw_ui_raid_transition.build_raid_end_screen(self, self.get_screen_frame("raid_end"))

    def _build_splash(self):
        f = self.get_screen_frame("splash")
        tk.Label(f, text="Escape the Wasteland", fg="#00FF00", bg="#111111", font=("Courier", 36, "bold")).pack(expand=True, pady=(50, 0))
        tk.Label(f, text="created by Ascent", fg="#FF0000", bg="#111111", font=("Courier", 10, "italic")).pack(pady=(0, 20))
        tk.Label(f, text=VERSION, fg="#00FF00", bg="#111111", font=("Courier", 8)).place(relx=0.01, rely=0.99, anchor="sw")
        tk.Button(f, text="Begin your Escape", command=self.begin_escape_sequence, bg="#003300", fg="#00FF00", font=("Courier", 16, "bold"), width=20, height=2).pack(pady=50)

    def _build_intro_screen(self):
        f = self.get_screen_frame("intro")
        self.intro_text_container = tk.Frame(f, bg="#111111")
        self.intro_text_container.place(relx=0.5, rely=0.4, anchor="center")
        self.intro_btn = tk.Button(f, text="CONTINUE", command=self._handle_intro_click, bg="#333333", fg="#FFFFFF", font=("Courier", 12, "bold"))
        self.intro_btn.place(relx=0.5, rely=0.85, anchor="center")

    def show_intro_screen(self):
        self.lift_screen("intro")
        self.intro_active = True
        self.intro_skipped = False
        self.intro_step = 0
        for w in self.intro_text_container.winfo_children(): w.destroy()
        self._animate_intro_line()

    def _animate_intro_line(self):
        if not self.intro_active or self.intro_skipped: return
        if self.intro_step < len(INTRO_TEXT):
            line = INTRO_TEXT[self.intro_step]
            lbl = tk.Label(self.intro_text_container, text=line, fg="#00FF00", bg="#111111", font=("Courier", 12))
            lbl.pack(pady=5)
            self.intro_step += 1
            self.after(800, self._animate_intro_line)
        else:
            self.intro_skipped = True

    def _handle_intro_click(self):
        if not self.intro_skipped:
            self.intro_skipped = True
            for w in self.intro_text_container.winfo_children(): w.destroy()
            for line in INTRO_TEXT:
                tk.Label(self.intro_text_container, text=line, fg="#00FF00", bg="#111111", font=("Courier", 12)).pack(pady=5)
        else:
            self.start_character_gen()

    def show_splash(self): self.lift_screen("splash")
    
    def begin_escape_sequence(self):
        if not self.save_data.get("game_install_path"):
            messagebox.showinfo("Setup Required", "Welcome to ETW.\n\nPlease select your Fallout 3 installation directory to continue.")
            path = filedialog.askdirectory(title="Select Fallout 3 Directory")
            if path:
                self.save_data["game_install_path"] = path
                engine.save_save_data(self.save_data)
                if hasattr(self, 'path_display_label'): self.path_display_label.config(text=path)
            else:
                return
        
        # MOVED: Resume Check Logic Here
        if self.save_data.get("raid_active"):
            self._prompt_resume_raid()
        elif not self.save_data.get("character"):
            self.show_intro_screen()
        else:
            self.show_town_screen()
            self._check_startup_buff_state()

    def show_town_screen(self):
        etw_ui_town.update_town_stats(self)
        self.raid_depart_btn.config(state="normal", text="Depart on Raid", bg="#003300")
        self.lift_screen("town")

    def show_game_screen(self):
        import etw_ui_quests, etw_ui_game
        self.quest_display_page = 0 
        etw_ui_game.refresh_pending_tasks_game(self, self.task_frame)
        etw_ui_game.refresh_raid_quest_hud(self, self.main_quest_frame)
        etw_ui_game.refresh_extractions(self)
        etw_ui_town.update_raid_condition_labels(self)
        etw_ui_game.update_active_buffs_display_raid(self)
        etw_ui_game.update_companion_raid_hud(self) 
        
        if not self.save_data.get("raid_active"):
            self.extracted_button.config(state="disabled")
            self.died_button.config(state="disabled")
            self.sos_button.config(state="disabled")
            self.debug_raid_time_btn.config(state="disabled")
        else:
            self.extracted_button.config(state="normal")
            self.died_button.config(state="normal")
            self.debug_raid_time_btn.config(state="normal")
        self.lift_screen("game")

    def show_quest_log_screen(self):
        etw_ui_quests.refresh_quest_log_screen(self)
        self.lift_screen("quest_log")

    def show_shop_screen(self):
        etw_ui_shop.refresh_shop_ui(self)
        self.lift_screen("shop")

    def show_inventory_screen(self):
        etw_ui_inventory.refresh_inventory_ui(self)
        self.lift_screen("inventory")

    def show_hideout_screen(self):
        etw_ui_hideout.refresh_hideout_ui(self)
        self.lift_screen("hideout")

    def show_bar_screen(self):
        etw_ui_bar.refresh_bar_ui(self)
        self.lift_screen("bar")

    def show_settings_screen(self, next_screen=None):
        import etw_ui_settings
        if next_screen:
            self.settings_next_screen = next_screen 
        self.path_display_label.config(text=self.save_data.get("game_install_path", "Not Set"))
        self.lift_screen("settings")
        
    def show_character_info_screen(self):
        etw_ui_charinfo.refresh_character_info_ui(self)
        self.lift_screen("character_info")
        
    def start_character_gen(self):
        etw_ui_chargen.start_character_gen(self)

    # -----------------------
    # RAID LIFECYCLE (ASYNC POLLING REFACTOR)
    # -----------------------
    def start_raid(self):
        import etw_ui_raid_transition
        self.lift_screen("departing")
        etw_ui_raid_transition.update_depart_status(self, "Scanning Vitals...")
        path = self.save_data.get("game_install_path")
        
        # Step 1: Trigger Baseline Scan if buffs enabled
        if path and self.save_data.get("companion_buffs", False):
            bridge.trigger_baseline_scan(path)
            # Enter Non-Blocking Polling Loop
            self._poll_raid_scan_results(start_time=time.time())
        else:
            # Skip scan, go straight to teleport
            self.after(1000, self._start_raid_sequence_3)

    def _poll_raid_scan_results(self, start_time):
        """
        Polls for the baseline scan file without freezing the UI.
        """
        path = self.save_data.get("game_install_path")
        
        # NON-BLOCKING READ
        res = bridge.read_baseline_scan(path, blocking=False)
        
        if res:
            # SUCCESS: File found and read
            if "baseline" not in self.save_data: self.save_data["baseline"] = {}
            self.save_data["baseline"].update(res["stats"])
            inventory.perform_full_inventory_sync(self.save_data)
            
            # Proceed to Step 2 (Buff Application)
            self._start_raid_sequence_buffs()
            
        else:
            # FAILURE/WAITING
            elapsed = time.time() - start_time
            if elapsed > 15.0:
                # Timeout - Proceed anyway to avoid softlock, but log/notify
                print("Raid Start: Scan Timed Out. Proceeding without fresh baseline.")
                self._start_raid_sequence_buffs()
            else:
                # Schedule next check in 100ms
                self.after(100, lambda: self._poll_raid_scan_results(start_time))

    def _start_raid_sequence_buffs(self):
        """
        Formerly _start_raid_sequence_2. Now applies buffs and transitions to teleport.
        """
        import etw_ui_raid_transition
        etw_ui_raid_transition.update_depart_status(self, "Injecting Stims (Buffs)...")
        buff_manager.apply_companion_buffs(self.save_data)
        
        # Give game 2 seconds to process buff commands before teleporting
        # Commands are fire-and-forget, but we want them to register before load screen.
        self.after(2000, self._start_raid_sequence_3)

    def _start_raid_sequence_3(self):
        """
        Final Step: Teleport to Raid Location.
        """
        import etw_ui_raid_transition
        etw_ui_raid_transition.update_depart_status(self, "Transmitting Coordinates...")
        spawn = raid.process_raid_start(self.save_data)
        if spawn:
            msg = f"Destination: {spawn['destination']}"
            etw_ui_raid_transition.update_depart_status(self, msg)
        
        # Short wait to let user read destination
        self.after(2000, self.show_game_screen)

    def use_sos_flare(self):
        if not self.save_data.get("raid_active"): return
        res = raid.use_sos_flare(self.save_data)
        if not res["success"]:
            self.show_temporary_text(self.raid_condition_raid_label, res["message"], "#FF0000")
            return
        self.show_temporary_text(self.raid_condition_raid_label, "FLARE FIRED! EXTRACTION INBOUND...", "#FFFF00")
        self.handle_extraction(is_sos=True)

    def handle_extraction(self, is_sos=False):
        self.reset_pause_state()
        context = raid.prepare_extraction(self.save_data, is_sos=is_sos)
        self.pending_raid_context = context
        self.lift_screen("raid_end")
        etw_ui_raid_transition.animate_raid_end_sequence(self, context)

    def handle_death(self):
        self.reset_pause_state()
        context = raid.prepare_death(self.save_data)
        self.pending_raid_context = context
        self.lift_screen("raid_end")
        etw_ui_raid_transition.animate_raid_end_sequence(self, context)

    def finalize_raid_end(self):
        raid.finalize_raid_teleport(self.save_data)
        self.pending_raid_context = None
        self.show_town_screen()

    def update_raid_timer(self):
        status = game_timer.process_game_tick(self.save_data)
        if status["is_active"]:
            elapsed = status["elapsed_seconds"]
            if status["is_paused"]:
                self.raid_timer_label.config(text="PAUSED", fg="#FFFF00")
            else:
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                self.raid_timer_label.config(text=f"Raid time: {mins:02}:{secs:02}")
                
                # --- NEW AMBUSH LOGIC ---
                if status["ambush_triggered"]:
                    # 1. Lock Target Location
                    ambush_data = ambush.prepare_ambush_coords(self.save_data)
                    
                    if ambush_data:
                        # 2. Show Warning
                        self.show_temporary_text(self.raid_condition_raid_label, "AMBUSH IMMINENT! HOLD POSITION...", "#FF0000", 3000)
                        
                        # 3. Random Delay (3-8 seconds)
                        delay_ms = random.randint(3000, 8000)
                        
                        # 4. Schedule Strike
                        self.after(delay_ms, lambda: ambush.execute_ambush_spawn(self.save_data, ambush_data))
                    else:
                        print("Ambush Warning: Could not prepare coords (Game paused or bridge busy?)")

                etw_ui_game.update_companion_raid_hud(self)
                if self.sos_button.winfo_exists():
                    self.sos_button.config(text=status["sos_text"], state=status["sos_state"])
                    if status["sos_ready"]: self.sos_button.config(bg="#AA5500")
                    else: self.sos_button.config(bg="#331100")
                if status["fail_state"]:
                    self.died_button.config(text=status["fail_state"])
                    if "FAILED" in status["fail_state"]:
                        self.extracted_button.config(state="disabled")
                    else:
                        self.extracted_button.config(state="normal")
                else:
                    self.died_button.config(text="DIED")
                    self.extracted_button.config(state="normal")

        if hasattr(self, 'town_threat_canvas') and self.town_threat_canvas.winfo_exists():
            threat = self.save_data.get("threat_level", 1)
            w = 100
            pct = min(1.0, threat / 5.0)
            self.town_threat_canvas.coords(self.town_threat_rect, 0, 0, int(w * pct), 15)
            col = "#00FF00"
            if threat >= 3: col = "#FFFF00"
            if threat >= 5: col = "#FF0000"
            self.town_threat_canvas.itemconfig(self.town_threat_rect, fill=col)
            
        if hasattr(self, 'raid_threat_canvas') and self.raid_threat_canvas.winfo_exists():
            threat = self.save_data.get("threat_level", 1)
            w_r = 200
            pct = min(1.0, threat / 5.0)
            self.raid_threat_canvas.coords(self.raid_threat_rect, 0, 0, int(w_r * pct), 15)
            col = "#00FF00"
            if threat >= 3: col = "#FFFF00"
            if threat >= 5: col = "#FF0000"
            self.raid_threat_canvas.itemconfig(self.raid_threat_rect, fill=col)

        self.after(1000, self.update_raid_timer)

    def reset_pause_state(self):
        self.save_data["raid_paused"] = False
        self.save_data["raid_paused_elapsed"] = 0.0
        if hasattr(self, 'raid_pause_button') and self.raid_pause_button.winfo_exists():
            self.raid_pause_button.config(text="Pause")
        engine.save_save_data(self.save_data)

    def register_wrappable(self, label):
        label.config(wraplength=self.current_wrap_width)
        self.wrappable_labels.append(label)

    def on_window_resize(self, event):
        if event.widget == self:
            if self._resize_job: self.after_cancel(self._resize_job)
            self._resize_job = self.after(100, lambda: self._perform_resize(event))

    def _perform_resize(self, event):
        self.current_wrap_width = max(event.width - 50, 200)
        for lbl in self.wrappable_labels:
            if lbl.winfo_exists():
                lbl.config(wraplength=self.current_wrap_width)

    def show_temporary_text(self, label, text, color="#00FF00", duration=2000):
        if not hasattr(label, '_original_text'): 
            label._original_text = label.cget("text")
            if "Active" not in label._original_text and "Scrip" not in label._original_text:
                label._original_text = ""
        label.config(text=text, fg=color)
        def revert():
            if label.winfo_exists(): 
                label.config(text=label._original_text, fg="#AAAAAA" if "Active" in label._original_text else "#00FF00")
        self.after(duration, revert)

if __name__ == "__main__":
    try:
        app = EscapeTheWastelandApp()
        app.mainloop()
    except Exception as e:
        # Last ditch logging for startup crash
        with open(ERROR_LOG_FILE, "a") as f:
            f.write("\n" + "="*60 + "\n")
            f.write(f"FATAL STARTUP CRASH at {datetime.datetime.now()}\n")
            f.write(str(e) + "\n")
            traceback.print_exc(file=f)
        raise e