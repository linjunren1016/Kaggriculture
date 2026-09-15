"""
核实 9 月高分 agent 的雇工使用，并统计逐日作物/牲畜变化量。

疑点：前面看到「雇工全程 0」，与 V38 的 13 个雇工反差极大。
需要确认是观测口径问题还是真的不雇工。

同时统计每日新增（用于反推规则）：
  - 每天买入多少动物 / 买几次地 / 种多少
"""
import csv
import json
import pickle
import statistics
from collections import Counter, defaultdict

reps = pickle.load(open("_docx/sept_replays.pkl", "rb"))
meta = {}
with open("_docx/sept_targets.csv", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        meta[row["episode_id"]] = row

out = ["核实雇工与逐日增量", ""]

# 1) 每个 agent：整局雇工峰值、CARE 次数、HIRE 次数、BUY_ANIMAL 次数
out.append("=== 每局的雇工与牲畜相关动作 ===")
out.append(f"{'episode':>10} {'峰值雇工':>8} {'HIRE订单':>9} {'BUY_ANIMAL':>11} "
           f"{'BUILD_PAST':>11} {'CARE':>6} {'FEED':>6} {'PICKUP':>7} {'资金':>9}")
rows = []
for eid, raw in reps.items():
    d = json.loads(raw) if isinstance(raw, str) else raw
    seat = int(meta.get(eid, {}).get("seat", 0))
    steps = d.get("steps", [])
    peak_hands = 0
    ops = Counter()
    market = Counter()
    for st in steps:
        obs = st[seat].get("observation") or {}
        farms = obs.get("farms")
        if farms:
            peak_hands = max(peak_hands, len(farms[seat].get("hands", []) or []))
        a = st[seat].get("action") or {}
        f = a.get("farmer")
        if isinstance(f, list) and f:
            ops[f[0]] += 1
        for h in a.get("hands") or []:
            if isinstance(h, list) and h:
                ops[h[0]] += 1
        for m in a.get("market") or []:
            if m:
                market[m[0]] += 1
    bank = float(meta.get(eid, {}).get("bank", 0))
    rows.append((eid, peak_hands, market.get("HIRE", 0), market.get("BUY_ANIMAL", 0),
                 ops.get("BUILD_PASTURE", 0), ops.get("CARE", 0), ops.get("FEED", 0),
                 ops.get("PICKUP", 0), bank))
for r in sorted(rows, key=lambda x: -x[8]):
    out.append(f"{r[0]:>10} {r[1]:>8} {r[2]:>9} {r[3]:>11} {r[4]:>11} "
               f"{r[5]:>6} {r[6]:>6} {r[7]:>7} {r[8]:>9,.0f}")

out.append("")
out.append(f"峰值雇工 均值: {statistics.mean(r[1] for r in rows):.2f}")
out.append(f"HIRE 订单 均值: {statistics.mean(r[2] for r in rows):.1f}")
out.append(f"BUY_ANIMAL 均值: {statistics.mean(r[3] for r in rows):.1f}")
out.append(f"BUILD_PASTURE 均值: {statistics.mean(r[4] for r in rows):.1f}")
out.append(f"CARE 均值: {statistics.mean(r[5] for r in rows):.1f}")
out.append(f"FEED 均值: {statistics.mean(r[6] for r in rows):.1f}")

# 2) 逐日净增量（取第一个 agent 做样例 + 均值）
out.append("")
out.append("=== 逐日净增量（12 个均值）===")
DAYS = list(range(0, 30, 2))
delta = defaultdict(lambda: defaultdict(list))
for eid, raw in reps.items():
    d = json.loads(raw) if isinstance(raw, str) else raw
    seat = int(meta.get(eid, {}).get("seat", 0))
    steps = d.get("steps", [])
    prev = None
    for day in DAYS:
        idx = min(day * 24, len(steps) - 1)
        obs = steps[idx][seat].get("observation") or {}
        farms = obs.get("farms")
        if not farms:
            continue
        farm = farms[seat]
        tiles = farm.get("tiles", [])
        crops = animals = 0
        for row2 in tiles:
            for t in row2:
                if isinstance(t, dict):
                    if t.get("kind") == "PLANT":
                        crops += 1
                    elif t.get("animal"):
                        animals += 1
        cur = {"crops": crops, "animals": animals,
               "land": len(farm.get("unlocked_quadrants", []) or []),
               "money": farm.get("money", 0)}
        if prev:
            for k in cur:
                delta[day][k].append(cur[k] - prev[k])
        prev = cur

hdr = f"{'day':>4} {'Δ作物':>7} {'Δ牲畜':>7} {'Δ象限':>7} {'Δ资金':>10}"
out.append(hdr)
out.append("-" * len(hdr))
for day in DAYS[1:]:
    a = delta.get(day)
    if not a or not a.get("crops"):
        continue
    out.append(f"{day:>4} {statistics.mean(a['crops']):>7.1f} "
               f"{statistics.mean(a['animals']):>7.1f} "
               f"{statistics.mean(a['land']):>7.2f} "
               f"{statistics.mean(a['money']):>10,.0f}")

text = "\n".join(out)
with open("_docx/sept_verify.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
