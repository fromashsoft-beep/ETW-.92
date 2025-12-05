try:
    import keyboard
except ImportError:
    print("WARNING: 'keyboard' module not installed. Hotkeys disabled.")
    keyboard = None

import time
import etw_bridge as bridge

class GlobalHotkeyManager:
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.hotkey_hook = None
        self.is_enabled = False
        
        # Load initial state from save data
        # If 'enable_f5_hotkey' is not in save data, default to True
        settings = self.app.save_data.get("user_settings", {})
        self.is_enabled = settings.get("enable_f5_hotkey", True)
        
        self.refresh_hooks()

    def set_enabled(self, enabled):
        """
        Toggles the F5 listener. Called by the Settings UI.
        """
        self.is_enabled = enabled
        
        # Update save data
        if "user_settings" not in self.app.save_data:
            self.app.save_data["user_settings"] = {}
        self.app.save_data["user_settings"]["enable_f5_hotkey"] = enabled
        
        self.refresh_hooks()

    def refresh_hooks(self):
        """
        Registers or unregisters the global F5 hook based on state.
        """
        if not keyboard: return
        
        # Always clear existing first
        self.cleanup()
        
        if self.is_enabled:
            try:
                # Register F5 to trigger the scan
                # We use root.after to ensure thread safety with Tkinter UI updates
                self.hotkey_hook = keyboard.add_hotkey("f5", lambda: self.root.after(0, self.handle_f5_press))
                # print("Global F5 Hotkey: ACTIVE")
            except Exception as e:
                print(f"Hotkey Error: {e}")

    def cleanup(self):
        """
        Removes all hooks. Safe to call on shutdown.
        """
        if keyboard:
            try:
                keyboard.unhook_all_hotkeys()
            except:
                pass
            self.hotkey_hook = None

    def handle_f5_press(self):
        """
        The actual action triggered by F5.
        Triggers a manual baseline scan if the app path is set.
        """
        game_path = self.app.save_data.get("game_install_path", "")
        if not game_path: 
            return

        # Trigger Scan
        bridge.trigger_baseline_scan(game_path)
        
        # Start Non-Blocking Polling Loop
        # We pass the start time to handle timeouts
        self.root.after(100, lambda: self._poll_scan_result(time.time()))

    def _poll_scan_result(self, start_time):
        """
        Polls for the scan result without freezing the main thread.
        """
        game_path = self.app.save_data.get("game_install_path", "")
        
        # NON-BLOCKING READ
        result = bridge.read_baseline_scan(game_path, blocking=False)
        
        if result:
            # SUCCESS: File found and read
            if "baseline" not in self.app.save_data: 
                self.app.save_data["baseline"] = {}
                
            self.app.save_data["baseline"]["level"] = result["level"]
            self.app.save_data["baseline"].update(result["stats"])
            
            # Optional: Visual feedback if we had access to a status bar
            # print("F5 Scan Complete: Baseline Updated")
            
        else:
            # WAITING or TIMEOUT
            elapsed = time.time() - start_time
            if elapsed > 15.0:
                print("F5 Scan Timeout: File not found.")
            else:
                # Schedule next check in 100ms
                self.root.after(100, lambda: self._poll_scan_result(start_time))