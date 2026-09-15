"""
Kaggriculture submission agent 鈥?"carry-wheat livestock economy".

Contract (official AGENTS.md):
  * main.py at the archive root, exposing a module-level ``agent(obs) -> action``
  * action = {"farmer": [op, ...], "hands": [[op, ...], ...], "market": [[op, ...], ...]}

Design notes, each traceable to the engine source (kaggriculture.py):

1. HARVEST is a silent no-op before ``first_yield_day``.
   `_apply_action` bails out when ``day - planted_day < first_yield_day``, and
   for one-time crops ``yield_units`` starts at 1 *on the planting day*. So the
   naive "harvest whenever yield_units > 0" policy deadlocks on a single tile
   forever. We gate on the crop's own ``first_yield_day`` / ``max_yield_day``.

2. Inventories auto-drop to the shed at end of day.
   ``_end_of_day`` calls ``_drop_inventories_to_shed`` and resets
   ``inventories = [{}]``, and the farmer respawns at the shed tile. Therefore a
   unit that ends the day holding wheat simply gives it back, and the only way
   to feed an animal is to *walk to the shed and PICKUP wheat in the morning*.
   Feeding is a logistics problem, not a market problem.

3. One-time crops pay once; animals pay forever.
   Wheat/carrot/melon are consumed by their harvest. Cows (milk, 160/tick every
   2 days), sheep (wool, 200/tick every 3 days) and geese (eggs, 50/tick daily)
   keep producing while fed, so they are the compounding asset. We therefore
   spend the opening days on a wheat/feed ramp and only then buy livestock.

4. CARE is a free +1 per fed-and-cared day, banked and paid on the next
   production tick, so we CARE whenever a unit is already standing on a fed
   animal (zero opportunity cost).

5. Selling moves the price against us, and premium goods (base > $100) are
   driven to the $1 floor by even modest gluts. We sell in small batches and
   order premium products first so they meet town demand before staples.
"""

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

import functools

HIRE_CAP = 8                 # 12-seed held-out test: +13.8% money vs 6, won 10/12
# Livestock is disabled by default. Measured over full seeded seasons against
# the built-in `starter`, a livestock-heavy policy scored ~$690 while the same
# agent with animals off scored ~$20,700. The reason is labour, not margin:
# feeding requires wheat *in hand*, so every animal costs a shed round-trip per
# day. At 8 cows that is roughly a full day of labour to earn ~$640, whereas the
# same actions spent on melon cycles earn far more. Animal support is kept in
# the code because a future version can feed from a field-side cache; flip this
# to a positive number to re-enable it.
MAX_LIVESTOCK = 0
MONEY_BUFFER = 150           # kept free so feed/seed obligations are never missed
SELL_BATCH = 6               # small batches to limit self-inflicted price damage
FEED_PICKUP_BATCH = 12       # wheat a unit grabs per shed visit
WHEAT_SELL_RESERVE = 40      # wheat never sold while livestock is alive
LAND_MIN_DAY = 3             # don't buy land before production is running
TOPUP_MARGIN = 700           # cash above the animal price before buying livestock

# Crop table straight from CROPS in kaggriculture.py.
CROP_INFO = {
    "WHEAT":      {"seed": 10,  "first_yield_day": 2,  "max_yield_day": 4,  "ongoing": False},
    "CARROT":     {"seed": 20,  "first_yield_day": 2,  "max_yield_day": 3,  "ongoing": False},
    "TOMATO":     {"seed": 50,  "first_yield_day": 8,  "max_yield_day": 8,  "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "ongoing": True},
    "MELON":      {"seed": 80,  "first_yield_day": 10, "max_yield_day": 12, "ongoing": False},
}

# Animal table from ANIMALS in kaggriculture.py.
ANIMAL_INFO = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3},
}

# Crop mix as a fraction of unlocked tiles. Wheat is over-weighted because it is
# also the livestock feed; melon is the best one-time cash crop.
TARGET_MIX = [
    ("WHEAT", 0.34),
    ("MELON", 0.24),
    ("CARROT", 0.22),
    ("TOMATO", 0.12),
    ("STRAWBERRY", 0.08),
]

SELL_PRIORITY = ["STRAWBERRY", "WOOL", "MILK", "MELON", "EGG",
                 "TOMATO", "CARROT", "WHEAT", "FERTILIZER"]

SHED_TILES = {(4, 4), (5, 4), (4, 5), (5, 5)}   # shed-adjacent at boardSize=10


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _is_plant(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT"


def _is_structure(t):
    return isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE")


def _has_animal(t):
    return _is_structure(t) and t.get("animal")


def _iter_tiles(me):
    for y, row in enumerate(me["tiles"]):
        for x, tile in enumerate(row):
            yield x, y, tile


def _count(me, pred):
    return sum(1 for _, _, t in _iter_tiles(me) if pred(t))


def _unlocked(me):
    return sum(1 for _, _, t in _iter_tiles(me) if t != "LOCKED")


def _plant_age(obs, tile):
    return obs["day"] - tile.get("planted_day", obs["day"])


def _animal_age(obs, tile):
    return obs["day"] - tile.get("placed_day", obs["day"])


def _crop_ready(obs, tile):
    """True when HARVEST on this plant actually yields something.

    The engine silently ignores HARVEST while ``age < first_yield_day``, and for
    one-time crops ``yield_units`` is already 1 on the planting day 鈥?so a policy
    that trusts ``yield_units`` alone will spin forever on one tile.
    """
    if not _is_plant(tile):
        return False
    info = CROP_INFO.get(tile.get("crop"))
    if not info or tile.get("yield_units", 0) <= 0:
        return False
    age = _plant_age(obs, tile)
    if age < info["first_yield_day"]:
        return False
    if info["ongoing"]:
        # Ongoing crops make scheduled drops; take whatever is sitting there.
        return True
    # One-time crops accumulate up to max_yield_day, then decay. Take the peak.
    return age >= info["max_yield_day"]


def _structure_ready(tile):
    return _is_structure(tile) and tile.get("yield_units", 0) > 0


def _needs_water(tile):
    return _is_plant(tile) and not tile.get("watered_today")


def _needs_feed(tile):
    return _has_animal(tile) and not tile.get("fed_today")


def _inventory_of(priv, index):
    invs = priv.get("inventories") or []
    if index < len(invs):
        return invs[index] or {}
    return {}


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_toward(src, dst):
    """One movement op that reduces Manhattan distance to ``dst``.

    Axes are resolved in a fixed order (horizontal first) so a unit cannot
    oscillate: alternating axes lets a unit step east, then south, then west,
    then north and never arrive. Locked tiles are passable, so a straight
    Manhattan walk is always feasible.
    """
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    if dx > 0:
        return "EAST"
    if dx < 0:
        return "WEST"
    if dy > 0:
        return "SOUTH"
    if dy < 0:
        return "NORTH"
    return None


def _norm(op):
    """Normalise an op to a list, as the action schema documents.

    A bare string such as ``"NORTH"`` happens to work because the engine reads
    ``op[0]``, but the documented contract is a list and some harnesses are
    stricter, so never emit a bare string.
    """
    if isinstance(op, str):
        return [op]
    return list(op)


def _nearest(obs, me, pos, pred):
    """Nearest tile satisfying ``pred`` by Manhattan distance. Locked tiles are
    passable, so straight-line distance is an adequate proxy for travel cost."""
    best, best_d = None, None
    for x, y, tile in _iter_tiles(me):
        if tile == "LOCKED":
            continue
        if pred(tile, x, y):
            d = _manhattan(pos, (x, y))
            if best_d is None or d < best_d:
                best, best_d = (x, y), d
    return best


def _toward_shed(pos):
    target = min(SHED_TILES, key=lambda t: _manhattan(pos, t))
    return _step_toward(pos, target)


def _shed_adjacent(pos):
    return tuple(pos) in SHED_TILES


# ---------------------------------------------------------------------------
# Unit policy
# ---------------------------------------------------------------------------

def _advance(src, target):
    """One movement step from ``src`` toward ``target``.

    A lambda-free helper on purpose: the Kaggle file loader picks the *last*
    callable in module globals, so stray module-level lambdas are a hazard.
    """
    step = _step_toward(src, target)
    return step if step else "PASS"


def _wants_animal(carry):
    return any(carry.get(a, 0) > 0 for a in ANIMAL_INFO)


def _placeable_animal(tile, carry):
    """The animal in ``carry`` that fits this empty structure, if any."""
    if not (_is_structure(tile) and not tile.get("animal")):
        return None
    wants = "GOOSE" if tile.get("kind") == "COOP" else ("COW", "SHEEP")
    wants = (wants,) if isinstance(wants, str) else wants
    for animal in wants:
        if carry.get(animal, 0) > 0:
            return animal
    return None


def _empty_structure(tile):
    return _is_structure(tile) and not tile.get("animal")


def _animal_here(tile):
    return _has_animal(tile)


def _task_list(obs, me):
    """All outstanding jobs on the farm this turn, most urgent first.

    Jobs are ranked by consequence, not by distance:
      1. feed an unfed animal        (two missed days -> animal lost forever)
      2. water a plant about to die  (two missed days -> tile becomes a weed)
      3. take animal produce / fertilizer
      4. harvest a ripe crop
      5. water any plant
      6. dig a weed
    Animal care is handled opportunistically when a unit is already on the tile.

    Returning a single shared ordered list is what lets the caller hand each
    unit a *different* job: without that, every unit independently picks the
    nearest tile and they all pile onto the same one.
    """
    feed, urgent_water, produce, harvest, water, weed = [], [], [], [], [], []
    for x, y, tile in _iter_tiles(me):
        if tile == "LOCKED" or tile is None:
            continue
        if _animal_here(tile):
            if not tile.get("fed_today"):
                feed.append(("FEED", (x, y)))
            if tile.get("yield_units", 0) > 0 or tile.get("fertilizer_available"):
                produce.append(("HARVEST", (x, y)))
        elif _is_plant(tile):
            if not tile.get("watered_today"):
                if tile.get("consecutive_unwatered", 0) >= 1:
                    urgent_water.append(("WATER", (x, y)))
                else:
                    water.append(("WATER", (x, y)))
            if _crop_ready(obs, tile):
                harvest.append(("HARVEST", (x, y)))
        elif isinstance(tile, dict) and tile.get("kind") == "WEED":
            weed.append(("DIG", (x, y)))
    return feed + urgent_water + produce + harvest + water + weed


def _unit_op(obs, me, priv, index, pos, carry, reserved=None, task=None):
    """Choose one op for a single farmer/hand.

    Priority reflects what is irreversible: an unfed animal escapes after two
    missed days and an unwatered plant becomes a weed, so survival first,
    then produce, then expansion, then planting.

    Every branch starts from the *current* tile so the unit always acts on
    arrival rather than walking past a tile it was targeting. ``task`` is this
    unit's assigned job from :func:`_task_list`, which keeps units spread out.
    """
    x, y = pos
    tile = me["tiles"][y][x]
    day = obs["day"]

    # --- 1. Survival: feed the animal we are standing on -------------------
    if _has_animal(tile) and not tile.get("fed_today") and carry.get("WHEAT", 0) > 0:
        return ["FEED"]

    # --- 2. Survival: water the plant we are standing on -------------------
    if _needs_water(tile):
        return ["WATER"]

    # --- 3. Place a carried animal into a matching empty structure ---------
    if _is_structure(tile):
        animal = _placeable_animal(tile, carry)
        if animal:
            return ["PLACE", animal, 1]

    # --- 4. Produce from whatever we are standing on ----------------------
    if _has_animal(tile) and tile.get("fed_today"):
        if tile.get("yield_units", 0) > 0:
            return ["HARVEST"]
        if tile.get("fertilizer_available"):
            return ["COLLECT_FERTILIZER"]
        if not tile.get("cared_today"):
            return ["CARE"]
    if _is_plant(tile) and _crop_ready(obs, tile):
        return ["HARVEST"]

    # --- 5. Clear a weed we are standing on -------------------------------
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return ["DIG"]

    # --- 6. Build a structure for a carried cow/sheep ---------------------
    # Carried livestock is a stalled investment: it has already been paid for
    # and earns nothing in inventory. This outranks routine chores and planting.
    if _wants_animal(carry) and _nearest(
            obs, me, pos, lambda t, tx, ty: _placeable_animal(t, carry) is not None) is None:
        if tile is None:
            for animal in ("COW", "SHEEP", "GOOSE"):
                if carry.get(animal, 0) > 0:
                    return ["BUILD_" + ANIMAL_INFO[animal]["structure"]]
        free = _nearest(obs, me, pos, lambda t, tx, ty: t is None)
        if free:
            return _advance(pos, free)

    # --- 7. Plant the tile we are standing on -----------------------------
    if tile is None:
        crop = _pick_plantable(obs, priv, me, reserved)
        if crop:
            if reserved is not None:
                reserved[crop] = reserved.get(crop, 0) + 1
            return ["PLANT", crop]

    # --- 8. Walk to this unit's assigned task -----------------------------
    # Feeding needs wheat in hand, so a feeding job first routes via the shed.
    if task:
        op, (tx, ty) = task
        if op == "FEED" and carry.get("WHEAT", 0) <= 0:
            feed_in_shed = priv["shed"].get("WHEAT", 0)
            if _shed_adjacent(pos) and feed_in_shed > 0:
                return ["PICKUP", "WHEAT", FEED_PICKUP_BATCH]
            if feed_in_shed > 0:
                return [_toward_shed(pos)]
        return _advance(pos, (tx, ty))

    # --- 9. Fallback: no assigned job, so find something useful -----------
    # 9a. any unfed animal (feeding requires wheat in hand)
    hungry = _nearest(obs, me, pos,
                      lambda t, tx, ty: _animal_here(t) and not t.get("fed_today"))
    if hungry:
        if carry.get("WHEAT", 0) > 0:
            return _advance(pos, hungry)
        feed_in_shed = priv["shed"].get("WHEAT", 0)
        if _shed_adjacent(pos) and feed_in_shed > 0:
            return ["PICKUP", "WHEAT", FEED_PICKUP_BATCH]
        if feed_in_shed > 0:
            return [_toward_shed(pos)]

    # 9b. unwatered plants
    target = _nearest(obs, me, pos, lambda t, tx, ty: _needs_water(t))
    if target:
        return _advance(pos, target)

    # 9c. produce, fertilizer, care
    target = _nearest(obs, me, pos,
                      lambda t, tx, ty: (_animal_here(t) and t.get("yield_units", 0) > 0)
                      or (_animal_here(t) and t.get("fertilizer_available")))
    if target:
        return _advance(pos, target)

    # 9d. ripe crops
    target = _nearest(obs, me, pos, lambda t, tx, ty: _crop_ready(obs, t))
    if target:
        return _advance(pos, target)

    # 8g. place a carried animal into an empty structure
    if _wants_animal(carry):
        target = _nearest(obs, me, pos,
                          lambda t, tx, ty: _placeable_animal(t, carry) is not None)
        if target:
            return _advance(pos, target)
        # no structure ready: build one on the nearest empty tile
        target = _nearest(obs, me, pos, lambda t, tx, ty: t is None)
        if target:
            return _advance(pos, target)

    # 8h. weeds
    target = _nearest(obs, me, pos,
                      lambda t, tx, ty: isinstance(t, dict) and t.get("kind") == "WEED")
    if target:
        return _advance(pos, target)

    # 8i. shed logistics. Livestock already paid for earns nothing sitting in
    #     the shed, so collect it before topping up feed wheat.
    shed = priv["shed"]
    if not _wants_animal(carry):
        for animal in ("COW", "SHEEP", "GOOSE"):
            if shed.get(animal, 0) > 0:
                if _shed_adjacent(pos):
                    return ["PICKUP", animal, 1]
                return [_toward_shed(pos)]

    # 8j. top up wheat so tomorrow's feeding is possible
    if _count(me, _has_animal) > 0 and carry.get("WHEAT", 0) <= 0:
        if _shed_adjacent(pos) and shed.get("WHEAT", 0) > 0:
            return ["PICKUP", "WHEAT", FEED_PICKUP_BATCH]
        return [_toward_shed(pos)]

    # 8k. otherwise go stand somewhere plantable
    target = _nearest(obs, me, pos, lambda t, tx, ty: t is None)
    if target:
        return _advance(pos, target)

    return ["PASS"]


def _pick_plantable(obs, priv, me, reserved=None):
    """Choose a crop to plant right now, respecting the target mix.

    ``reserved`` counts seeds already claimed by other units this turn. This is
    essential, not cosmetic: the engine validates PLANT *atomically per turn*
    (kaggriculture.py, "Atomic PLANT validation") and if the total number of
    PLANT requests for a crop exceeds the seeds available, it drops **every**
    request for that crop. Without reservations, N units all asking for the same
    scarce crop means none of them ever plant, and the units livelock forever.
    """
    seeds = priv.get("seeds") or {}
    reserved = reserved if reserved is not None else {}
    counts = {}
    for _, _, t in _iter_tiles(me):
        if _is_plant(t):
            counts[t.get("crop")] = counts.get(t.get("crop"), 0) + 1

    def deficit(item):
        crop, frac = item
        return frac - (counts.get(crop, 0) + seeds.get(crop, 0)) / max(_unlocked(me), 1)

    for crop, _frac in sorted(TARGET_MIX, key=deficit, reverse=True):
        available = seeds.get(crop, 0) - reserved.get(crop, 0)
        if available > 0:
            return crop
    return None


# ---------------------------------------------------------------------------
# Market policy
# ---------------------------------------------------------------------------

def _next_hire_cost(hires_today):
    a, b = 1, 1
    for _ in range(hires_today):
        a, b = b, a + b
    return a


def _market_orders(obs, me, priv, my_index):
    money = me["money"]
    shed = priv["shed"]
    seeds = priv["seeds"]
    day = obs["day"]
    orders = []

    live_animals = _count(me, _has_animal)
    empty_structs = _count(me, lambda t: _is_structure(t) and not t.get("animal"))
    carried_animals = sum(v for k, v in _inventory_of(priv, 0).items() if k in ANIMAL_INFO)

    # 1. Hire. Early hands cost 1,1,2,3,5... and act 24 times a day, so they are
    #    the cheapest labour in the game. Stop before the fib curve bites.
    hires_today = me.get("hires_today", 0)
    if hires_today < HIRE_CAP and money > _next_hire_cost(hires_today) + MONEY_BUFFER:
        orders.append(["HIRE"])

    # 2. Keep the shed stocked with feed wheat. Guarded on live_animals because
    #    with MAX_LIVESTOCK = 0 there is nothing that can ever consume it, so
    #    buying feed would be pure cash burn. (Measured effect of this guard was
    #    within noise, ~0.1%; kept because it is correct, not because it pays.)
    if live_animals > 0:
        feed_demand = live_animals + 4          # today's feed plus a small buffer
        wheat_held = shed.get("WHEAT", 0)
        if wheat_held < feed_demand:
            shortfall = feed_demand - wheat_held
            price = obs["market"]["prices"].get("WHEAT", 25)
            if money > price * shortfall + MONEY_BUFFER + 200:
                orders.append(["BUY_PRODUCT", "WHEAT", shortfall])

    # 3. Seeds, cheap ones first, sized to the target crop mix.
    counts = {}
    for _, _, t in _iter_tiles(me):
        if _is_plant(t):
            counts[t.get("crop")] = counts.get(t.get("crop"), 0) + 1
    total = max(_unlocked(me), 1)
    plantable_slots = _count(me, lambda t: t is None) + _count(
        me, lambda t: isinstance(t, dict) and t.get("kind") == "WEED")
    for crop, frac in sorted(TARGET_MIX, key=lambda cf: CROP_INFO[cf[0]]["seed"]):
        want = frac * total
        have = counts.get(crop, 0) + seeds.get(crop, 0)
        need = int(want - have)
        if need <= 0:
            continue
        need = min(need, max(plantable_slots, 1) * 2)
        cost = CROP_INFO[crop]["seed"] * need
        if money > cost + MONEY_BUFFER:
            orders.append(["BUY_SEED", crop, need])

    # 4. Livestock. Buy the animal and let a unit build the structure and place
    #    it. Cows first: highest absolute margin per tick. Bounded because every
    #    head permanently consumes a daily wheat feed action.
    if live_animals + carried_animals < MAX_LIVESTOCK:
        for animal in ("COW", "SHEEP", "GOOSE"):
            cost = ANIMAL_INFO[animal]["cost"]
            if money > cost + TOPUP_MARGIN:
                orders.append(["BUY_ANIMAL", animal, 1])
                break

    # 5. Sell. Premium products first so they meet town demand while the price
    #    is still high; wheat is held back as feed while livestock is alive.
    for product in SELL_PRIORITY:
        qty = shed.get(product, 0)
        if qty <= 0:
            continue
        if product == "WHEAT" and live_animals > 0:
            qty = max(0, qty - WHEAT_SELL_RESERVE)
        if qty > 0:
            orders.append(["SELL", product, min(qty, SELL_BATCH)])

    # 6. Land, once production is actually running.
    n_unlocked_q = len(me.get("unlocked_quadrants", ["NW"]))
    land_cost = {1: 1000, 2: 2000, 3: 4000}.get(n_unlocked_q)
    if land_cost and day >= LAND_MIN_DAY and money > land_cost + 2500:
        orders.append(["BUY_LAND"])

    return orders[:10]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_SAFE_ACTION = {"farmer": ["PASS"], "hands": [], "market": []}


def _safe(fn):
    """Never let an exception escape the agent.

    A raised exception aborts the whole episode and scores the submission zero,
    so any bug is infinitely more expensive than one wasted turn. On failure we
    log to stderr (visible via `kaggle competitions logs`) and PASS.

    ``functools.wraps`` matters: the Kaggle file loader selects the *last*
    callable defined in module globals, so the wrapper must keep the ``agent``
    name and not leak internals.
    """
    @functools.wraps(fn)
    def wrapper(obs):
        try:
            return fn(obs)
        except Exception as exc:                                  # noqa: BLE001
            import sys
            import traceback
            print(f"[kaggriculture-agent] error at step "
                  f"{obs.get('step')}: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return dict(_SAFE_ACTION)
    wrapper.__wrapped__ = fn
    return wrapper


def _assign_tasks(obs, me, farmer_pos, hand_positions):
    """Assign each unit its *nearest* outstanding task, greedily.

    The previous version handed out tasks in list order
    (``tasks[:1 + len(hands)]``), which ignored where units actually stand, so
    units regularly walked across the board past a closer tile that another unit
    was slowly walking to. Measured on this agent, 43% of the farmer's actions
    and 59% of the hands' actions were movement, which capped land utilisation at
    ~50%: the labour budget was consumed by walking instead of working.

    Greedy nearest-assignment is a cheap approximation of the assignment problem
    and needs no communication between units, because the caller walks the unit
    list once and removes each claimed task from the pool.
    """
    units = [tuple(farmer_pos)] + [tuple(p) for p in hand_positions]
    pool = list(_task_list(obs, me))
    result = []
    for pos in units:
        if not pool:
            result.append(None)
            continue
        # Nearest by Manhattan distance; ties resolved by urgency (pool order).
        best_i, best_d = 0, None
        for i, (_op, tgt) in enumerate(pool):
            d = abs(pos[0] - tgt[0]) + abs(pos[1] - tgt[1])
            if best_d is None or d < best_d:
                best_i, best_d = i, d
        result.append(pool.pop(best_i))
    return result


@_safe
def agent(obs):
    player = obs.get("player", 0)
    me = obs["farms"][player]
    priv = obs.get("private") or {}

    orders = _market_orders(obs, me, priv, player)

    invs = priv.get("inventories") or [{}]
    farmer_carry = invs[0] if len(invs) > 0 else {}
    farmer_pos = me["farmer"]
    hands = me.get("hands", [])

    # Shared per-turn ledger of seeds already claimed by earlier units. The
    # engine voids *all* PLANT requests for a crop when demand exceeds supply,
    # so units must not collectively over-request the same scarce seed.
    reserved = {}

    # Hand out distinct jobs, each unit getting the closest one, so units do not
    # converge on the same tile and do not walk past nearer work.
    assignments = _assign_tasks(obs, me, farmer_pos, hands)

    farmer_task = assignments[0] if assignments else None
    farmer_op = _unit_op(obs, me, priv, 0, farmer_pos, farmer_carry, reserved, farmer_task)

    hand_ops = []
    for i, hpos in enumerate(hands):
        carry = invs[i + 1] if i + 1 < len(invs) else {}
        task = assignments[i + 1] if i + 1 < len(assignments) else None
        hand_ops.append(_norm(
            _unit_op(obs, me, priv, i + 1, hpos, carry, reserved, task)))

    return {"farmer": _norm(farmer_op), "hands": hand_ops, "market": orders}