import etw_io as io
import etw_config as config

# ----------------------------------------------------------------------
# DIALOGUE MANAGER
# ----------------------------------------------------------------------

_NPC_CACHE = None

def _load_npc_data():
    global _NPC_CACHE
    if _NPC_CACHE is None:
        _NPC_CACHE = io.load_json(config.PATHS["content_npcs"], {})
    return _NPC_CACHE

def get_intro_text():
    data = _load_npc_data()
    return data.get("intro_sequence", [])

def get_npc_data(npc_id):
    data = _load_npc_data()
    return data.get("npcs", {}).get(npc_id, {})

def get_dialogue(npc_id, key, default="..."):
    npc = get_npc_data(npc_id)
    return npc.get("dialogue", {}).get(key, default)