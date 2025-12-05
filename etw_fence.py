import json
import os
import random
import math
import etw_engine as engine
import etw_stats as stats # NEW: Required for reputation calculation
import etw_loot as loot_logic # NEW: Required for loot pool access

# ----------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ----------------------------------------------------------------------
FENCE_SHOP_FILE = "fence_shop.json"

# Reputation-based Rarity Tables (Tier 1 to Tier 4 percentages)
REP_RARITY_TABLE = {
    "1-2":  {"tier_1": 60, "tier_2": 30, "tier_3": 9,  "tier_4": 1},
    "3-5":  {"tier_1": 40, "tier_2": 40, "tier_3": 17, "tier_4": 3},
    "6-8":  {"tier_1": 25, "tier_2": 40, "tier_3": 25, "tier_4": 10},
    "9-10": {"tier_1": 10, "tier_2": 35, "tier_3": 35, "tier_4": 20}
}

# Category Weights for Slot Rolling
BUY_SLOT_WEIGHTS = {"ammo": 30, "consumable": 35, "weapon": 15, "armor": 10, "misc": 10}
SELL_SLOT_WEIGHTS = {"misc": 65, "ammo": 15, "consumable": 10, "weapon": 5, "armor": 5}

# Base Multipliers for Value Calculation
# Adjusted: Ammo reduced to 3 (Significant reduction as requested)
CATEGORY_BASE_VALUES = {
    "weapon": 40, "armor": 35, "consumable": 20, "ammo": 3, "misc": 15
}
RARITY_MULT = {"tier_1": 0.6, "tier_2": 1.0, "tier_3": 1.6, "tier_4": 2.4}

# Tag Multipliers (Utility Cues)
# Buy Slots (Fence -> Player): Prioritize utility
BUY_TAG_MULTS = {
    "medical": 3.0, "component": 3.0, "tech": 3.0, "ballistic": 3.0, "energy": 3.0,
    "chem": 2.0, "food": 1.0, "drink": 1.0, "junk": 0.5, "toy": 0.5
}
# Sell Slots (Player -> Fence): Prioritize logical valuables
SELL_TAG_MULTS = {
    "valuable": 3.0, "component": 3.0, "tech": 3.0,
    "medical": 2.0, "junk": 1.0, "toy": 1.0
}

# Scrip Pricing Constant (Divisor) - Tuning target: Common junk < 1-2 scrip
PRICE_DIVISOR_K = 18.0
MIN_SCRIP = 1
MAX_SCRIP = 500

# Budget Configuration
BASE_BUDGET = 200
BUDGET_REP_SCALING = 50 # Per Rep point

# Refresh Cost Base
REFRESH_COST_BASE = 50
REFRESH_COST_REP_SCALING = 50 # Cost increases with Rep (Gating high yields)

# ----------------------------------------------------------------------
# PERSISTENCE
# ----------------------------------------------------------------------
def load_fence_shop():
    if not os.path.exists(FENCE_SHOP_FILE):
        return None 
    try:
        with open(FENCE_SHOP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def save_fence_shop(data):
    with open(FENCE_SHOP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ----------------------------------------------------------------------
# CORE GENERATION LOGIC
# ----------------------------------------------------------------------
def refresh_shop(save_data):
    """
    Main entry point to refresh inventory.
    Deducts caps (handled by caller or UI check), re-rolls items, resets budget.
    """
    # FIX: Call stats.compute_reputation directly
    rep = stats.compute_reputation(save_data)
    
    # 1. Roll Buy Slots (10)
    buy_slots = []
    for _ in range(10):
        item = _roll_single_item(rep, "buy")
        if item: buy_slots.append(item)
        
    # 2. Roll Sell Slots (10) with Validation (6-8 Misc)
    sell_slots = []
    valid = False
    attempts = 0
    
    while not valid and attempts < 50:
        attempts += 1
        temp_slots = []
        misc_count = 0
        
        for _ in range(10):
            item = _roll_single_item(rep, "sell")
            if item:
                temp_slots.append(item)
                if item["category"] == "misc": misc_count += 1
        
        if 6 <= misc_count <= 8:
            sell_slots = temp_slots
            valid = True
    
    # Fallback if validation fails repeatedly (unlikely given weights)
    if not valid:
        sell_slots = temp_slots

    # 3. Calculate Budget
    # Formula: Base + (Rep * Scaling)
    budget = int(BASE_BUDGET + (rep * BUDGET_REP_SCALING))
    
    shop_data = {
        "buy_slots": buy_slots,
        "sell_slots": sell_slots,
        "scrip_budget": budget,
        "max_budget": budget,
        "last_refresh_rep": rep
    }
    
    save_fence_shop(shop_data)
    return shop_data

def get_refresh_cost(save_data):
    # FIX: Call stats.compute_reputation directly
    rep = stats.compute_reputation(save_data)
    # Low rep = Cheap. High rep = Expensive.
    return int(REFRESH_COST_BASE + (rep * REFRESH_COST_REP_SCALING))

# ----------------------------------------------------------------------
# ITEM ROLLING INTERNALS
# ----------------------------------------------------------------------
def _get_rep_band_key(rep):
    if rep <= 2: return "1-2"
    if rep <= 5: return "3-5"
    if rep <= 8: return "6-8"
    return "9-10"

def _roll_category(mode):
    weights = BUY_SLOT_WEIGHTS if mode == "buy" else SELL_SLOT_WEIGHTS
    cats = list(weights.keys())
    vals = list(weights.values())
    return random.choices(cats, weights=vals, k=1)[0]

def _roll_rarity(rep):
    band = _get_rep_band_key(rep)
    table = REP_RARITY_TABLE[band]
    tiers = list(table.keys())
    probs = list(table.values())
    return random.choices(tiers, weights=probs, k=1)[0]

def _roll_single_item(rep, mode):
    """
    Selects an item from the global pool based on Rep/Mode constraints.
    Calculates Price and Quantity immediately.
    """
    # 1. Determine constraints
    category = _roll_category(mode)
    rarity = _roll_rarity(rep)
    
    # 2. Fetch candidates
    # FIX: Use loot_logic import directly
    pool_data = loot_logic.get_loot_pool_cached() 
    
    # Note: engine.get_loot_pool_cached structures items by category names like "weapon" (singular)
    # but some json files might use plural. We rely on the 'category' field in JSON.
    candidates = pool_data["by_category"].get(category, [])
    
    # Filter by Rarity
    tier_candidates = [i for i in candidates if i.get("rarity") == rarity]
    
    # Fallback logic if tier is empty for that category
    if not tier_candidates:
        tier_candidates = candidates # Relax rarity
    
    if not tier_candidates:
        return None # Should not happen with full DB
        
    # 3. Select specific item using Tag Weights
    # We pick a subset to weigh against each other
    subset = random.sample(tier_candidates, min(len(tier_candidates), 5))
    
    best_item = None
    best_score = -1
    
    tag_mults = BUY_TAG_MULTS if mode == "buy" else SELL_TAG_MULTS
    
    # Weighted random selection could be better, but spec implies "Prioritize"
    # We will use weighted choice from the subset
    item_weights = []
    for item in subset:
        score = 1.0
        # Check primary tag
        tag = item.get("tag")
        if tag in tag_mults: score = tag_mults[tag]
        
        # Check list tags if 'tag' is missing or generic
        if "tags" in item:
            for t in item["tags"]:
                if t in tag_mults: score = max(score, tag_mults[t])
        
        item_weights.append(score)
    
    selected_item = random.choices(subset, weights=item_weights, k=1)[0]
    
    # 4. Calculate Quantity
    qty = _calculate_quantity(selected_item, rep, mode)
    
    # 5. Calculate Price (Unit Price)
    unit_price = _calculate_price(selected_item, rep, mode)
    
    return {
        "code": selected_item["code"],
        "name": selected_item["name"],
        "category": category,
        "rarity": rarity,
        "qty": qty,
        "unit_scrip_cost": unit_price,
        "total_scrip_cost": unit_price * qty
    }

def _calculate_quantity(item, rep, mode):
    cat = item.get("category")
    
    if mode == "buy": # Fence Selling to Player
        if cat in ["weapon", "armor"]: return 1
        if cat == "ammo":
            # Rep scaling -> 20-80+
            base = 20
            scaling = int(rep * 6) # at rep 10 -> +60 -> 80
            return base + scaling + random.randint(0, 10)
        if cat in ["consumable", "chem"]: # JSON uses "consumable", Logic uses specific checks
            # High rep up to 4-6
            limit = 2
            if rep >= 5: limit = 4
            if rep >= 8: limit = 6
            return random.randint(1, limit)
        if cat == "misc":
            limit = 3
            if rep >= 6: limit = 5
            return random.randint(1, limit)
            
    else: # Fence Buying from Player (Sell Slots)
        if cat in ["weapon", "armor"]: return 1
        if cat == "misc":
            # 3-10+ depending on rep
            base = 3
            bonus = int(rep * 0.8)
            return base + bonus + random.randint(0, 3)
        if cat == "ammo":
            # 12-90
            base = 12
            bonus = int(rep * 8)
            return base + bonus + random.randint(0, 10)
        if cat == "consumable":
            return random.randint(1, 8)
            
    return 1

def _calculate_price(item, rep, mode):
    # 1. Base Value Calculation
    cat = item.get("category", "misc")
    cat_base = CATEGORY_BASE_VALUES.get(cat, 15)
    
    rar = item.get("rarity", "tier_1")
    r_mult = RARITY_MULT.get(rar, 1.0)
    
    # Determine max tag mult
    t_mult = 1.0
    # Use BUY weights generally for intrinsic value, or split? 
    # Spec says "base_value = cat * rarity * tag". The tag multipliers in the spec
    # are defined under "TAG WEIGHTS" which has Buy and Sell sections.
    # Logic implies intrinsic value shouldn't flip-flop wildly, but let's use the 
    # multiplier associated with the mode to reflect "Fence's value of the item".
    tag_ref = BUY_TAG_MULTS if mode == "buy" else SELL_TAG_MULTS
    
    tag = item.get("tag")
    if tag in tag_ref: t_mult = tag_ref[tag]
    if "tags" in item:
        for t in item["tags"]:
            if t in tag_ref: t_mult = max(t_mult, tag_ref[t])
            
    base_value = cat_base * r_mult * t_mult
    
    # 2. Scale to Scrip
    base_scrip = round(base_value / PRICE_DIVISOR_K)
    base_scrip = max(MIN_SCRIP, min(MAX_SCRIP, base_scrip))
    
    # 3. Apply Rep Discount/Markup
    # rep_discount = (rep - 1) * 1% (0.01)
    rep_discount = max(0, (rep - 1) * 0.01)
    
    final_price = 0
    if mode == "buy": # Fence -> Player
        # fence_sale_price = base * 1.30 * (1 - rep_discount)
        final_price = base_scrip * 1.30 * (1.0 - rep_discount)
    else: # Player -> Fence
        # fence_buy_price = base * 0.50 * (1 + rep_discount)
        # Note: Spec says (1 + rep_discount) for buying, meaning he pays MORE at high rep. Correct.
        final_price = base_scrip * 0.50 * (1.0 + rep_discount)
        
    return max(1, int(final_price))

# ----------------------------------------------------------------------
# TRANSACTION HELPERS
# ----------------------------------------------------------------------
def perform_fence_buy(save_data, slot_index):
    """
    Player BUYING from Fence.
    """
    shop = load_fence_shop()
    if not shop: return False, "Shop not initialized."
    
    slots = shop.get("buy_slots", [])
    if slot_index < 0 or slot_index >= len(slots): return False, "Invalid slot."
    
    item = slots[slot_index]
    if not item: return False, "Slot empty."
    
    cost = item["total_scrip_cost"]
    if save_data.get("scrip", 0) < cost: return False, "Not enough Scrip."
    
    # Transaction
    save_data["scrip"] -= cost
    engine._process_game_commands([f"player.additem {item['code']} {item['qty']}"])
    
    # Clear Slot
    slots[slot_index] = None
    shop["buy_slots"] = slots
    save_fence_shop(shop)
    
    return True, f"Bought {item['name']} (x{item['qty']})"

def perform_fence_sell(save_data, slot_index):
    """
    Player SELLING to Fence.
    Requires item in inventory (game console command needed to remove).
    """
    shop = load_fence_shop()
    if not shop: return False, "Shop not initialized."
    
    slots = shop.get("sell_slots", [])
    if slot_index < 0 or slot_index >= len(slots): return False, "Invalid slot."
    
    item = slots[slot_index]
    if not item: return False, "Slot empty."
    
    payout = item["total_scrip_cost"]
    budget = shop.get("scrip_budget", 0)
    
    # Budget Check
    if budget <= 0:
        return False, "Fence is out of funds. Refresh required."
    
    final_payout = payout
    if payout > budget:
        # Option B from Spec: Reduce to floor/partial? 
        # Spec: "Payouts stop entirely OR Reduce to floor".
        # Let's implement Stop Entirely for simplicity and strict gating.
        return False, f"Fence funds too low ({budget} remaining)."
    
    # Remove item from player (Blind fire command, we assume player has it based on roleplay or we rely on honor system?)
    # The app cannot check player inventory. This is an "Honor System" trade or we just assume.
    # Given the app structure, we usually assume valid state if button clicked, but we should send the remove command.
    
    engine._process_game_commands([f"player.removeitem {item['code']} {item['qty']}"])
    save_data["scrip"] += final_payout
    
    # Deduct Budget
    shop["scrip_budget"] -= final_payout
    
    # Clear Slot
    slots[slot_index] = None
    shop["sell_slots"] = slots
    save_fence_shop(shop)
    
    return True, f"Sold {item['name']} for {final_payout} Scrip."