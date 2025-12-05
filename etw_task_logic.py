# Foundation
import etw_config as config
import etw_io as io

# Note: UI Modules are imported INSIDE functions to prevent Circular Dependency crashes.
# This ensures the UI is fully loaded before we try to refresh it.

# ----------------------------------------------------------------------
# QUEST PROGRESSION LOGIC (Static Quests)
# ----------------------------------------------------------------------

def tick_static_quest_objective(app, q_id, obj_idx):
    """
    Marks a specific static quest objective as complete in the save data.
    """
    if "quest_progress" not in app.save_data: app.save_data["quest_progress"] = {}
    
    key = str(q_id)
    current_list = app.save_data["quest_progress"].get(key, [])
    
    while len(current_list) <= obj_idx: current_list.append(False)
    
    current_list[obj_idx] = True
    app.save_data["quest_progress"][key] = current_list
    
    io.save_json(config.PATHS["save_data"], app.save_data)
    
    # REFRESH UI
    _refresh_ui_safely(app)


# ----------------------------------------------------------------------
# CONTRACT PROGRESSION LOGIC (Dynamic Tasks/Quests)
# ----------------------------------------------------------------------

def tick_dynamic_task_objective(app, task, obj_idx, is_quest=False):
    """
    Decrements objective counter for a dynamic task or quest objective.
    """
    if is_quest:
        raw_objs = task.get("raw_objectives", [])
        if obj_idx >= len(raw_objs): return
        target_obj_list = raw_objs
        
    else: # Active Contract/Task
        current_objs = task.get("objectives", [])
        if obj_idx >= len(current_objs): return
        target_obj_list = current_objs

    # Update Data
    cur = target_obj_list[obj_idx][3]
    if cur > 0:
        target_obj_list[obj_idx][3] = cur - 1
        
    if target_obj_list[obj_idx][3] <= 0:
        # Sync static tracking for Side Quests
        if is_quest:
            q_id = task.get("id")
            if q_id:
                tick_static_quest_objective(app, q_id, obj_idx) 
                return # tick_static handles the save/refresh, so we can exit
    
    # Check Completion (Contracts only)
    if not is_quest:
        all_done = True
        for o in target_obj_list:
            if o[3] > 0: all_done = False; break
            
        if all_done: 
            task["ready_to_complete"] = True
    
    io.save_json(config.PATHS["save_data"], app.save_data)

    # REFRESH UI
    _refresh_ui_safely(app)

# ----------------------------------------------------------------------
# UI REFRESH HELPER
# ----------------------------------------------------------------------

def _refresh_ui_safely(app):
    """
    Imports UI modules locally to avoid circular dependency loops.
    """
    try:
        import etw_ui_quests as quests_ui
        import etw_ui_game as game_ui
        
        screen = app.get_active_screen_name()
        
        if screen == "game":
            if hasattr(app, 'task_frame'):
                game_ui.refresh_pending_tasks_game(app, app.task_frame)
            if hasattr(app, 'main_quest_frame'):
                game_ui.refresh_raid_quest_hud(app, app.main_quest_frame)
                
        elif screen == "quest_log":
            quests_ui.refresh_quest_log_screen(app)
            
    except ImportError:
        print("Warning: UI Refresh skipped due to import error.")
    except Exception as e:
        print(f"UI Refresh Error: {e}")