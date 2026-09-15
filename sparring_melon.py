"""
sparring_melon.py —— 本地陪练 Agent（第二策略）

用途
----
`main.py` 在本地只能测内置的 pass / random / starter，而那三个太弱，
已经 15-0 全胜，没有区分度。这个陪练提供第二套策略思路，用来做真实对抗。

策略差异（和 main.py 刻意不同）
------------------------------
1. 价格感知的出售。用真实的价格函数算「多卖 1 个的边际收益」，
   卖到边际收益低于阈值就停手，避免自己把价格砸到 1 元地板。
   main.py 是固定批量卖，没有这个判断。
2. 作物配比按「每地块每天的净收益」算，而不是拍脑袋定的比例。
   重点押在价格抗跌的作物上。
3. 更激进的扩张：早期就买地、多雇工，赌规模收益。
4. 不养牲畜（理由同 main.py：喂食需要仓库往返，人工成本太高）。

这个文件只用于本地评测，不提交。
"""
import functools

# ---------------------------------------------------------------------------
# 价格模型（来自官方 README 的 Price Function 表）
# ---------------------------------------------------------------------------
I0 = 10000

# resource: (base, T, below_func, below_target, above_func, above_target)
MARKET_PARAMS = {
    "WHEAT":      (25,  400, "sqrt",   0.80, "log",    0.20),
    "CARROT":     (35,  450, "hinge",  1.00, "sqrt",   0.70),
    "TOMATO":     (60,  200, "hinge",  0.40, "sqrt",   0.60),
    "STRAWBERRY": (120, 100, "sqrt",   0.70, "linear", 1.60),
    "MELON":      (250, 300, "log",    0.20, "sq",     3.60),
    "EGG":        (50,  332, "hinge",  0.40, "log",    0.20),
    "MILK":       (160, 122, "sqrt",   0.60, "linear", 1.60),
    "WOOL":       (200, 105, "log",    0.20, "sq",     3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}


def _shape(name, x, T):
    if name == "linear":
        return x / T
    if name == "sq":
        return (x / T) ** 2
    if name == "sqrt":
        return (x / T) ** 0.5
    if name == "log":
        import math
        return math.log1p(x)
    if name == "log10":
        import math
        return math.log10(1 + x)
    if name == "hinge":
        u = x / T
        return u + 8 * max(0.0, u - 1.0) ** 2
    raise ValueError(name)


@functools.lru_cache(maxsize=8192)
def price(resource, inventory):
    """官方价格函数：base + sign * amp * f(|inv - I0|)，下限 1，四舍五入。"""
    base, T, bf, bt, af, at = MARKET_PARAMS[resource]
    if inventory < I0:
        f, target, sign = bf, bt, 1
        x = I0 - inventory
    else:
        f, target, sign = af, at, -1
        x = inventory - I0
    amp = target * base / _shape(f, T, T)
    return max(1, int(round(base + sign * amp * _shape(f, x, T))))


@functools.lru_cache(maxsize=4096)
def marginal_revenue(resource, start_inv, units):
    """卖出 units 个的总收入（按官方 per-unit 顺序报价，价格随卖出递减）。"""
    total = 0
    inv = start_inv
    for _ in range(units):
        total += price(resource, inv)
        inv += 1
    return total


@functools.lru_cache(maxsize=4096)
def best_sell_units(resource, start_inv, max_units, floor_price):
    """在价格跌到 floor_price 之前，最多该卖多少个。"""
    inv = start_inv
    n = 0
    for _ in range(max_units):
        if price(resource, inv) < floor_price:
            break
        inv += 1
        n += 1
    return n


# ---------------------------------------------------------------------------
# 作物经济性：每地块每天的净收益（用真实价格函数估算）
# ---------------------------------------------------------------------------
CROPS = {
    # crop: (seed, first_yield_day, max_yield_day, max_yield, ongoing)
    "WHEAT":      (10,  2,  4,  6, False),
    "CARROT":     (20,  2,  3,  4, False),
    "TOMATO":     (50,  8,  8,  4, True),
    "STRAWBERRY": (100, 10, 10, 4, True),
    "MELON":      (80,  10, 12, 6, False),
}


def crop_score(crop, horizon=30, typical_inv=None):
    """估算该作物从第 0 天起、在 horizon 天内每地块的总净收益。

    价格用「市场上已有一定供给」的保守估计，避免高估高级品。

    注意：这个分数只反映「最终收益」，不含现金占用成本。
    长周期作物（甜瓜、草莓）要压 10 天资金，现金紧张时先种它会导致
    买不起后续种子和雇工而全面停摆 —— 所以实际选种时还要叠加
    CASH_GATE 判断（见 _best_crop）。
    """
    seed, fyd, myd, maxyield, ongoing = CROPS[crop]
    inv = typical_inv or {}
    start = inv.get(crop, I0)
    cycles = 0
    revenue = 0.0
    day = 0
    # 一次性作物：占地 fyd+1 天左右到顶，max_lifespan 在 max_yield_day+1
    if not ongoing:
        cycle_len = myd + 2          # 收获后要 DIG 再种，留 2 天余量
        while day + myd <= horizon:
            revenue += marginal_revenue(crop, start, maxyield)
            start += maxyield
            day += cycle_len
            cycles += 1
            if cycles >= 8:
                break
        cost = seed * cycles
        return (revenue - cost) / horizon, cycles
    # 持续作物：首次产出后按间隔重复，最多 4 次
    per = maxyield
    while day + fyd <= horizon:
        revenue += marginal_revenue(crop, start, per)
        start += per
        day += (1 if crop == "TOMATO" else 2)
        cycles += 1
        if cycles >= 4:
            break
    cost = seed
    return (revenue - cost) / horizon, cycles


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------
HIRE_CAP = 7
SELL_FLOOR_RATIO = 0.55     # 价格跌破 base*该比例就停手
# 高级品的绝对块数上限。
# 注意不能用「占解锁地块的百分比」做上限：早期解锁地块少（25 块），
# 百分比上限只有 12 块，一触发就会把 MELON/STRAWBERRY/TOMATO 全部挡掉，
# 导致什么都不种（实测：只种 18 块地、65 块空地闲置）。
# 用绝对块数才能保证触发上限后自然降级到小麦继续铺满土地。
MAX_PREMIUM_TILES = 20      # 甜瓜 / 草莓合计上限
LAND_MIN_DAY = 1
MONEY_RESERVE = 120
SELL_ORDER = ["STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT"]

# 现金下限：任何时候都要留下这么多钱买种子 / 雇工。
# 没有这个保护，早期把钱全压在长周期作物上会让整个农场停摆
# （实测：day 3 剩 $19，之后 24 天买不起任何东西）。
CASH_FLOOR = 700

# 长周期作物需要压资金，现金不够时不许种。
# 价值：作物 -> 允许种植所需的最低现金（含现金下限）
# 门槛参考：甜瓜 10 天回本、草莓 10 天、番茄 8 天，都要压资金；
# 小麦 2 天、胡萝卜 2 天，是现金流的发动机，永远不设门槛。
CASH_GATE = {
    "WHEAT": 0,
    "CARROT": 0,
    "TOMATO": 600,
    "MELON": 1200,
    "STRAWBERRY": 1800,
}

SHED_TILES = {(4, 4), (5, 4), (4, 5), (5, 5)}


def _is_plant(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT"


def _iter(me):
    for y, row in enumerate(me["tiles"]):
        for x, t in enumerate(row):
            yield x, y, t


def _count(me, pred):
    return sum(1 for _, _, t in _iter(me) if pred(t))


def _unlocked(me):
    return sum(1 for _, _, t in _iter(me) if t != "LOCKED")


def _crop_ready(day, tile):
    info = CROPS.get(tile.get("crop"))
    if not info or tile.get("yield_units", 0) <= 0:
        return False
    age = day - tile.get("planted_day", day)
    seed, fyd, myd, maxyield, ongoing = info
    if age < fyd:
        return False
    return True if ongoing else age >= myd


def _needs_water(t):
    return _is_plant(t) and not t.get("watered_today")


def _nearest(me, pos, pred):
    best, bd = None, None
    for x, y, t in _iter(me):
        if t == "LOCKED":
            continue
        if pred(t):
            d = abs(pos[0] - x) + abs(pos[1] - y)
            if bd is None or d < bd:
                best, bd = (x, y), d
    return best


def _step(src, dst):
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    if dx > 0:
        return "EAST"
    if dx < 0:
        return "WEST"
    if dy > 0:
        return "SOUTH"
    if dy < 0:
        return "NORTH"
    return None


def _advance(src, dst):
    s = _step(src, dst)
    return [s] if s else ["PASS"]


def _toward_shed(pos):
    tgt = min(SHED_TILES, key=lambda t: abs(pos[0] - t[0]) + abs(pos[1] - t[1]))
    s = _step(pos, tgt)
    return [s] if s else ["PASS"]


def _best_crop(me, priv, reserved):
    """按每地块每天的净收益排序，返回还没种满、有种子余额、且现金允许的作物。

    现金门槛是必需的：作物分数只算最终收益，不算资金占用。
    甜瓜 / 草莓要压 10 天资金，现金不足时先种它们会导致后续全面停摆。
    """
    seeds = priv.get("seeds") or {}
    money = me["money"]

    counted = {}

    def _tiles_of(crop):
        if crop not in counted:
            counted[crop] = sum(1 for _, _, t in _iter(me)
                                if _is_plant(t) and t.get("crop") == crop)
        return counted[crop]

    def _blocked(crop):
        # 高级品配额用绝对块数，不用比例（比例上限会在早期把一切都挡死）
        if crop in ("MELON", "STRAWBERRY"):
            if _tiles_of("MELON") + _tiles_of("STRAWBERRY") >= MAX_PREMIUM_TILES:
                return True
        return False

    # 单位选种：和 _market 用同一套规则，避免两边标准不一致导致「买了种不下去」
    # 返回的是「作物名」，由调用方包装成动作 —— 早期版本这里有两种返回类型，
    # 导致调用方把它当作物名去索引 dict，抛 TypeError: unhashable type 后被
    # 安全兜底吞掉，整个 Agent 静默停摆。
    #
    # 注意：这里不检查 CASH_FLOOR。现金下限是给「买种子」用的，种植不花钱
    # （种子已经在手上）。早期把下限也用在种植上，导致资金一时低于下限就
    # 连库存里的小麦种子都不肯种，单位全部 PASS —— 实测资金冻结在 $2,359。
    focus = None
    for crop in sorted(CROPS, key=_cached_score, reverse=True):
        if _blocked(crop):
            continue
        if seeds.get(crop, 0) - reserved.get(crop, 0) <= 0:
            continue
        focus = crop
        break
    return focus


@functools.lru_cache(maxsize=32)
def _cached_score(crop):
    """带产能惩罚的作物评分。

    crop_score 在「市场只有少量同种供给」时算，但那对高级品过于乐观：
    在 100 格农场上规模化生产甜瓜 / 草莓，会把市场库存推高到 2T 以上，
    价格直接崩到 1 元地板（看官方价格表：MELON 在 I0+2T 就只剩 $1）。
    小麦的抗跌性最好（I0+2T 仍有 $19，是 log 型 glut 曲线），
    所以规模化时小麦的单位面积真实收益反而更高。

    这里加权模拟「达到足够产能后价格必然下滑」的效应。
    """
    score = crop_score(crop)[0]
    # 产能惩罚：单价越高、越依赖稀缺溢价的作物，被自己砸价的幅度越大
    FRAGILITY = {
        "WHEAT": 1.00,       # log 型 glut，几乎不崩
        "CARROT": 0.85,      # sqrt 型 glut，较抗跌
        "TOMATO": 0.70,
        "MELON": 0.45,       # sq 型 glut，极易崩
        "STRAWBERRY": 0.35,  # linear 型 glut 且 target 1.6，最易崩
    }
    return score * FRAGILITY[crop]


def _nominal_inventory():
    """市场初始库存（官方默认 I0 对每种商品一致）。"""
    return {c: I0 for c in MARKET_PARAMS}


# ---------------------------------------------------------------------------
# 单位策略
# ---------------------------------------------------------------------------
def _unit_op(day, me, priv, pos, carry, reserved):
    x, y = pos
    tile = me["tiles"][y][x]

    if _is_plant(tile):
        if not tile.get("watered_today"):
            return ["WATER"]
        if _crop_ready(day, tile):
            return ["HARVEST"]
    elif isinstance(tile, dict) and tile.get("kind") == "WEED":
        return ["DIG"]
    elif tile is None:
        crop = _best_crop(me, priv, reserved)
        if crop:
            reserved[crop] = reserved.get(crop, 0) + 1
            return ["PLANT", crop]

    # 优先救快死的作物
    tgt = _nearest(me, pos,
                   lambda t: _is_plant(t) and not t.get("watered_today")
                   and t.get("consecutive_unwatered", 0) >= 1)
    if tgt:
        return _advance(pos, tgt)

    # 先把成熟作物收掉：现金流优先，也让出地块给下一轮
    tgt = _nearest(me, pos, lambda t: _is_plant(t) and t.get("yield_units", 0) > 0
                   and _crop_ready(day, t))
    if tgt:
        return _advance(pos, tgt)

    # 再扩产：脚下不是空地时，走向最近的空地，别先跑去浇水。
    # 浇水虽然要紧，但"两天一次"就够，而地空着就是零产出。
    if tile is not None:
        tgt = _nearest(me, pos, lambda t: t is None)
        if tgt:
            return _advance(pos, tgt)

    tgt = _nearest(me, pos, _needs_water)
    if tgt:
        return _advance(pos, tgt)

    tgt = _nearest(me, pos, lambda t: isinstance(t, dict) and t.get("kind") == "WEED")
    if tgt:
        return _advance(pos, tgt)

    tgt = _nearest(me, pos, lambda t: t is None)
    if tgt:
        return _advance(pos, tgt)
    return ["PASS"]


# ---------------------------------------------------------------------------
# 市场策略
# ---------------------------------------------------------------------------
def _market(day, me, priv, obs):
    money = me["money"]
    shed = priv["shed"]
    seeds = priv["seeds"]
    prices = obs["market"]["prices"]
    inventory = obs["market"]["inventory"]
    orders = []

    # 雇工：斐波那契成本，早雇便宜
    n_hired = me.get("hires_today", 0)
    a, b = 1, 1
    for _ in range(n_hired):
        a, b = b, a + b
    if n_hired < HIRE_CAP and money > a + MONEY_RESERVE:
        orders.append(["HIRE"])

    # 买地：尽早扩张。土地是产能上限，晚买就是每天少种几十块地。
    # 条件放宽到「够钱 + 留一点缓冲」，不要等「很有钱」才买。
    nq = len(me.get("unlocked_quadrants", ["NW"]))
    land_cost = {1: 1000, 2: 2000, 3: 4000}.get(nq)
    if land_cost and day >= LAND_MIN_DAY and money > land_cost + 500:
        orders.append(["BUY_LAND"])

    # 种子采购：先确定「本回合打算重点种哪个作物」，只给它买种子。
    #
    # 之前的写法对每种作物都按全部空地算 want，结果开局一口气买了
    # MELON 12 + STRAWBERRY 12，把 1920 元压在 24 颗高级种子上，
    # 而高级作物的现金门槛之后再也够不着 —— 种子永远种不下去，钱全死掉。
    # 现在改成：按分数挑出当前现金允许的最好作物，只按它的实际缺口买。
    counts = {}
    for _, _, t in _iter(me):
        if _is_plant(t):
            counts[t.get("crop")] = counts.get(t.get("crop"), 0) + 1
    free_slots = _count(me, lambda t: t is None) + _count(
        me, lambda t: isinstance(t, dict) and t.get("kind") == "WEED")

    focus = None
    counted = {}

    def _tiles_of(crop):
        if crop not in counted:
            counted[crop] = counts.get(crop, 0)
        return counted[crop]

    for crop in sorted(CROPS, key=_cached_score, reverse=True):
        if money < CASH_GATE.get(crop, 0) + CASH_FLOOR:
            continue
        # 高级品配额用绝对块数，不用比例（比例上限会在早期把一切都挡死）
        if crop in ("MELON", "STRAWBERRY") and \
                _tiles_of("MELON") + _tiles_of("STRAWBERRY") >= MAX_PREMIUM_TILES:
            continue
        focus = crop
        break

    # 兜底：高级品达到配额后必须降级到速生作物继续铺满土地，
    # 否则 focus 变成 None，单位站着不动、空地看着不种。
    if focus is None:
        for crop in ("WHEAT", "CARROT"):
            if seeds.get(crop, 0) > 0 or money - CASH_FLOOR >= CROPS[crop][0]:
                focus = crop
                break

    if focus and free_slots > 0:
        held = seeds.get(focus, 0)
        want = max(0, min(free_slots, 8) - held)      # 一次最多补 8 颗
        seed_cost = CROPS[focus][0]
        budget = money - CASH_FLOOR
        afford = int(max(0, budget) // seed_cost)
        need = min(want, afford)
        if need > 0:
            orders.append(["BUY_SEED", focus, need])

    # 出售：价格感知，跌到 base*ratio 以下就停手
    for product in SELL_ORDER:
        have = shed.get(product, 0)
        if have <= 0:
            continue
        base = MARKET_PARAMS[product][0]
        floor = base * SELL_FLOOR_RATIO
        inv = inventory.get(product, I0)
        n = best_sell_units(product, inv, have, floor)
        if n > 0:
            orders.append(["SELL", product, n])

    return orders[:10]


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
_SAFE = {"farmer": ["PASS"], "hands": [], "market": []}


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(obs):
        try:
            return fn(obs)
        except Exception as exc:                                   # noqa: BLE001
            import sys
            print(f"[sparring] {type(exc).__name__}: {exc}", file=sys.stderr)
            return dict(_SAFE)
    wrapper.__wrapped__ = fn
    return wrapper


@_safe
def agent(obs):
    player = obs.get("player", 0)
    me = obs["farms"][player]
    priv = obs.get("private") or {}
    day = obs["day"]

    orders = _market(day, me, priv, obs)

    reserved = {}
    invs = priv.get("inventories") or [{}]
    farmer_op = _unit_op(day, me, priv, me["farmer"],
                         invs[0] if invs else {}, reserved)
    hand_ops = []
    for i, hpos in enumerate(me.get("hands", [])):
        carry = invs[i + 1] if i + 1 < len(invs) else {}
        hand_ops.append(_unit_op(day, me, priv, hpos, carry, reserved))

    def norm(op):
        return [op] if isinstance(op, str) else list(op)

    return {"farmer": norm(farmer_op), "hands": [norm(h) for h in hand_ops],
            "market": orders}
