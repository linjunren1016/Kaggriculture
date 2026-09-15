"""
把提取到的 9 月高分回放还原成 agent，并分析其行为（当前 meta）。

输入：_docx/sept_replays.pkl（{episode_id: replay_json}）
输出：opponents_src/sept/*.py  + 行为画像对比
"""
import importlib.util
import json
import os
import pickle
import sys
from collections import Counter

sys.path.insert(0, ".")
MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}
os.makedirs("opponents_src/sept", exist_ok=True)

TEMPLATE = '''"""
从官方回放还原的 9 月高分线上 agent（当前 meta）。

来源：Kaggle 公开数据集 georgymamarin/kaggriculture-episodes 的 replay parquet
episode {ep}  座位 {seat}  该局 rating_after={rating}  终局资金 {bank}
创建时间：{ct}

固定动作表还原：按 step 回放当时提交的动作。
仅用于本地评测对比。
"""

_TABLE = {table}


def _norm(op):
    return [op] if isinstance(op, str) else list(op)


def agent(obs):
    step = obs.get("step", 0)
    e = _TABLE.get(step)
    if e is None:
        return {{"farmer": ["PASS"], "hands": [], "market": []}}
    return {{"farmer": _norm(e["farmer"]),
             "hands": [_norm(h) for h in e["hands"]],
             "market": [list(m) for m in e["market"]]}}
'''


def norm_action(a):
    if not isinstance(a, dict):
        return None
    f = a.get("farmer")
    if isinstance(f, str):
        f = [f]
    hands = [h if isinstance(h, list) else [h] for h in (a.get("hands") or [])]
    market = [list(m) for m in (a.get("market") or [])]
    return {"farmer": f or ["PASS"], "hands": hands, "market": market}


# 目标元数据
meta = {}
with open("_docx/sept_targets.csv", encoding="utf-8") as fh:
    import csv
    for row in csv.DictReader(fh):
        meta[row["episode_id"]] = row

reps = pickle.load(open("_docx/sept_replays.pkl", "rb"))
out = ["9 月高分回放 → 本地 agent", ""]

built = []
for eid, raw in reps.items():
    t = meta.get(eid, {})
    seat = int(t.get("seat", 0))
    d = json.loads(raw) if isinstance(raw, str) else raw
    info = d.get("info", {})
    steps = d.get("steps", [])
    table = {}
    for i, st in enumerate(steps):
        if seat < len(st):
            na = norm_action(st[seat].get("action"))
            if na:
                table[i] = na
    fn = f"opponents_src/sept/sept_{eid}_s{seat}.py"
    with open(fn, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.format(
            ep=eid, seat=seat, rating=t.get("rating", "?"),
            bank=t.get("bank", "?"), ct=info.get("create_time", "?"),
            table=repr(table)))
    # 行为画像
    ops = Counter()
    market = Counter()
    for e in table.values():
        f = e.get("farmer") or []
        if f:
            ops[f[0]] += 1
        for h in e.get("hands") or []:
            if h:
                ops[h[0]] += 1
        for mk in e.get("market") or []:
            if mk:
                market[mk[0]] += 1
    total = sum(ops.values()) or 1
    prof = {
        "move": sum(v for k, v in ops.items() if k in MOVE) / total,
        "water": ops.get("WATER", 0) / total,
        "plant": ops.get("PLANT", 0) / total,
        "harvest": ops.get("HARVEST", 0) / total,
        "fert": ops.get("FERTILIZE", 0) / total,
        "care": ops.get("CARE", 0) / total,
        "pass": ops.get("PASS", 0) / total,
        "dig": ops.get("DIG", 0) / total,
    }
    built.append({"eid": eid, "seat": seat, "rating": t.get("rating"),
                  "bank": t.get("bank"), "prof": prof,
                  "ops": total, "market": market, "file": fn})
    out.append(f"  ep {eid} seat {seat}  rating {t.get('rating')}  bank {t.get('bank')}  "
               f"→ {fn}")

# 聚合画像
if built:
    keys = ("move", "water", "plant", "harvest", "fert", "care", "pass", "dig")
    out.append("")
    hdr = f"{'episode':>10} {'rating':>9} " + " ".join(f"{k:>7}" for k in keys) + "  SELL"
    out.append(hdr)
    out.append("-" * len(hdr))
    for b in built:
        p = b["prof"]
        out.append(f"{b['eid']:>10} {float(b['rating']):>9,.1f} "
                   + " ".join(f"{p[k]:>7.1%}" for k in keys)
                   + f"  {b['market'].get('SELL',0):>4}")
    out.append("")
    out.append("9 月高分 agent 平均签名：")
    for k in keys:
        import statistics
        out.append(f"  {k:<8} {statistics.mean(b['prof'][k] for b in built):>7.1%}")
    mk = Counter()
    for b in built:
        for k, v in b["market"].items():
            mk[k] += v
    out.append("")
    out.append("平均市场订单/局：")
    for k, v in mk.most_common():
        out.append(f"  {k:<14} {v/len(built):>8.1f}")

text = "\n".join(out)
with open("_docx/sept_agents.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
