"""
从 9 月高分回放反推「决策规则」。

此前只看了动作频次（浇水/移动…），那太粗。本脚本提取**逐日农场构成**：
  象限数、雇工数、作物数与分种、牧场合计、牲畜数与分种、资金
再与 V38 的本地轨迹对比，找出阶段性的规则差异。

数据来源：_docx/sept_replays.pkl（12 个 2,809-2,908 分 agent 的原局）
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

DAYS = [0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 28, 29]

out = ["9 月高分 agent 的逐日农场构成（从原局回放提取）", ""]

# 聚合每个采样日的均值
agg = defaultdict(lambda: defaultdict(list))
detail = []

for eid, raw in reps.items():
    d = json.loads(raw) if isinstance(raw, str) else raw
    seat = int(meta.get(eid, {}).get("seat", 0))
    steps = d.get("steps", [])
    per_day = {}
    for day in DAYS:
        idx = min(day * 24, len(steps) - 1)
        obs = steps[idx][seat].get("observation") or {}
        farms = obs.get("farms")
        if not farms:
            continue
        farm = farms[seat]
        tiles = farm.get("tiles", [])
        crops = Counter()
        animals = Counter()
        for row in tiles:
            for t in row:
                if isinstance(t, dict):
                    if t.get("kind") == "PLANT":
                        crops[t.get("crop")] += 1
                    elif t.get("animal"):
                        animals[t.get("animal")] += 1
        rec = {
            "land": len(farm.get("unlocked_quadrants", []) or []),
            "hands": len(farm.get("hands", []) or []),
            "crops": sum(crops.values()),
            "animals": sum(animals.values()),
            "money": farm.get("money", 0),
            "wheat": crops.get("WHEAT", 0),
            "straw": crops.get("STRAWBERRY", 0),
            "melon": crops.get("MELON", 0),
            "cow": animals.get("COW", 0),
            "sheep": animals.get("SHEEP", 0),
            "goose": animals.get("GOOSE", 0),
        }
        per_day[day] = rec
        for k, v in rec.items():
            agg[day][k].append(v)
    detail.append((eid, float(meta.get(eid, {}).get("rating", 0)), per_day))

out.append("=== 12 个 agent 的逐日均值 ===")
hdr = (f"{'day':>4} {'象限':>5} {'雇工':>5} {'作物':>5} {'小麦':>5} {'草莓':>5} "
       f"{'甜瓜':>5} {'牲畜':>5} {'牛':>4} {'羊':>4} {'鹅':>4} {'资金':>10}")
out.append(hdr)
out.append("-" * len(hdr))
for day in DAYS:
    a = agg.get(day)
    if not a or not a.get("land"):
        continue
    m = lambda k: statistics.mean(a[k]) if a.get(k) else 0
    out.append(f"{day:>4} {m('land'):>5.1f} {m('hands'):>5.1f} {m('crops'):>5.1f} "
               f"{m('wheat'):>5.1f} {m('straw'):>5.1f} {m('melon'):>5.1f} "
               f"{m('animals'):>5.1f} {m('cow'):>4.1f} {m('sheep'):>4.1f} "
               f"{m('goose'):>4.1f} {m('money'):>10,.0f}")

out.append("")
out.append("=== 终局（day 29）逐 agent 明细 ===")
out.append(f"{'episode':>10} {'rating':>9} {'象限':>5} {'作物':>5} {'小麦':>5} "
           f"{'草莓':>5} {'甜瓜':>5} {'牲畜':>5} {'牛':>4} {'羊':>4} {'资金':>10}")
for eid, rating, per_day in sorted(detail, key=lambda x: -x[1]):
    r = per_day.get(29) or per_day.get(28)
    if not r:
        continue
    out.append(f"{eid:>10} {rating:>9,.1f} {r['land']:>5} {r['crops']:>5} "
               f"{r['wheat']:>5} {r['straw']:>5} {r['melon']:>5} {r['animals']:>5} "
               f"{r['cow']:>4} {r['sheep']:>4} {r['money']:>10,.0f}")

# 关键规则：牲畜什么时候上、买地什么时候
out.append("")
out.append("=== 关键时点（均值）===")
for day in DAYS:
    a = agg.get(day)
    if not a or not a.get("animals"):
        continue
    an = statistics.mean(a["animals"])
    if day in (0, 2, 4, 6, 8, 10, 12, 16, 24, 29):
        out.append(f"  day {day:>2}: 牲畜 {an:>5.1f}   象限 "
                   f"{statistics.mean(a['land']):>4.1f}   雇工 "
                   f"{statistics.mean(a['hands']):>4.1f}")

text = "\n".join(out)
with open("_docx/sept_rules.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
