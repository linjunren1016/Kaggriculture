"""
跨 18 位玩家统计：什么行为对应更高的终局资金。

数据来自 9 局线上回放（含我方与各对手），全部是真实线上对局，不依赖任何复现。
目标：找出与"高资金"相关的结构特征，而不是靠单局印象。
"""
import glob
import json
import statistics
from collections import Counter

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}

players = []
for path in sorted(glob.glob("replays/episode-*-replay.json")):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    info = d.get("info", {})
    agents = [a.get("Name") for a in info.get("Agents", [])]
    rewards = d.get("rewards", [])
    steps = d["steps"]
    seed = info.get("seed")

    for p in (0, 1):
        ops = Counter()
        market = Counter()
        for st in steps:
            act = st[p].get("action")
            if not act:
                continue
            f = act.get("farmer")
            if isinstance(f, list) and f:
                ops[f[0]] += 1
            for h in act.get("hands", []) or []:
                if isinstance(h, list) and h:
                    ops[h[0]] += 1
            for m in act.get("market", []) or []:
                market[m[0]] += 1
        total = sum(ops.values())
        if not total:
            continue
        # 终局状态
        final = steps[-1][p].get("observation", {}) or {}
        farms = final.get("farms")
        n_plants = n_weeds = n_land = 0
        if farms:
            tiles = farms[p].get("tiles", [])
            n_plants = sum(1 for r in tiles for t in r
                           if isinstance(t, dict) and t.get("kind") == "PLANT")
            n_weeds = sum(1 for r in tiles for t in r
                          if isinstance(t, dict) and t.get("kind") == "WEED")
            n_land = len(farms[p].get("unlocked_quadrants", []) or [])

        # 雇工峰值
        peak_hands = 0
        for st in steps:
            o = st[p].get("observation", {}) or {}
            fa = o.get("farms")
            if fa:
                peak_hands = max(peak_hands, len(fa[p].get("hands", []) or []))

        players.append({
            "name": agents[p], "seed": seed, "money": rewards[p],
            "total": total,
            "move": sum(v for k, v in ops.items() if k in MOVE) / total,
            "water": ops.get("WATER", 0) / total,
            "plant_op": ops.get("PLANT", 0) / total,
            "harvest": ops.get("HARVEST", 0) / total,
            "dig": ops.get("DIG", 0) / total,
            "pass": ops.get("PASS", 0) / total,
            "hire": market.get("HIRE", 0),
            "buy_seed": market.get("BUY_SEED", 0),
            "sell": market.get("SELL", 0),
            "buy_land": market.get("BUY_LAND", 0),
            "plants": n_plants, "weeds": n_weeds, "land": n_land,
            "peak_hands": peak_hands,
        })

players.sort(key=lambda x: -x["money"])
med = statistics.median(p["money"] for p in players)

out = [f"跨 {len(players)} 位玩家的行为 vs 终局资金", f"（资金中位数 ${med:,.0f}）", ""]
hdr = (f"{'资金':>9} {'移动':>6} {'浇水':>6} {'种植':>6} {'收获':>6} {'挖草':>6} "
       f"{'PASS':>5} {'雇工峰':>6} {'买地':>4} {'终作物':>6} {'终杂草':>6}  玩家")
out.append(hdr)
out.append("-" * len(hdr))
for p in players:
    out.append(f"{p['money']:>9,.0f} {p['move']:>6.1%} {p['water']:>6.1%} "
               f"{p['plant_op']:>6.1%} {p['harvest']:>6.1%} {p['dig']:>6.1%} "
               f"{p['pass']:>5.1%} {p['peak_hands']:>6} {p['buy_land']:>4} "
               f"{p['plants']:>6} {p['weeds']:>6}  {p['name']}")

# 高分组 vs 低分组的均值差异
hi = [p for p in players if p["money"] >= med]
lo = [p for p in players if p["money"] < med]
out.append("")
out.append(f"高分组（≥中位，{len(hi)} 人） vs 低分组（{len(lo)} 人）均值：")
for key, label in [("move", "移动"), ("water", "浇水"), ("plant_op", "种植动作"),
                   ("harvest", "收获"), ("dig", "挖草"), ("pass", "PASS"),
                   ("peak_hands", "雇工峰值"), ("hire", "HIRE 订单"),
                   ("buy_land", "买地次数"), ("plants", "终局作物"), ("weeds", "终局杂草")]:
    h = statistics.mean(p[key] for p in hi)
    l = statistics.mean(p[key] for p in lo)
    out.append(f"  {label:<10} 高 {h:>8.2f}   低 {l:>8.2f}   差 {h-l:>+8.2f}")

with open("_docx/cross_players.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out))
