import json
import os

# ----------------------------------------------------------------------
# FILE I/O UTILITIES
# ----------------------------------------------------------------------
# This module handles all disk operations for JSON data.
# It is dependency-free to allow safe import by any module.

def load_json(path, default=None):
    """
    Safely loads a JSON file. Returns 'default' if file missing or corrupt.
    """
    if default is None: 
        default = {}
        
    if not os.path.exists(path): 
        return default
        
    try:
        with open(path, "r", encoding="utf-8") as f: 
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return default

def save_json(path, data):
    """
    Safely writes data to a JSON file using Atomic Save pattern.
    1. Writes to path.tmp
    2. Renames path.tmp -> path
    """
    temp_path = f"{path}.tmp"
    
    try:
        # Ensure directory exists if path contains folders
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        # Write to temporary file first
        with open(temp_path, "w", encoding="utf-8") as f: 
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno()) # Force write to disk
            
        # Atomic replacement
        os.replace(temp_path, path)
        return True
        
    except Exception as e:
        print(f"Error saving {path}: {e}")
        # Clean up temp file if it exists and failed
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
        return False