"""
分析已还原的高 rating agent 的动作表：它们的路线和我们有什么不同。

这些动作表是从官方回放里直接提取的（真实线上 agent 的行为），
因此这是「顶尖选手到底怎么打」的第一手证据，不需要再读 parquet。

对比维度：
  - 动作构成（浇水 / 移动 / 种植 / 收获 / 施肥 / 照料 / 挖草）
  - 市场订单构成（雇工 / 买种 / 买地 / 买动物 / 卖 / 买小麦）
  - 开局前 60 步在做什么
"""
import glob
import importlib.util
import os
import sys
from collections import Counter

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}
MINE = "candidates/V38.py"


def load_table(path):
    spec = importlib.util.spec_from_file_location("m", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return getattr(m, "_TABLE", None)


def profile(path, label, out):
    table = load_table(path)
    if not table:
        out.append(f"{label}: 无动作表")
        return None
    ops = Counter()
    market = Counter()
    for step, e in table.items():
        if not e:
            continue
        f = e.get("farmer") or []
        if f:
            ops[f[0]] += 1
        for h in e.get("hands") or []:
            if h:
                ops[h[0]] += 1
        for mk in e.get("market") or []:
            if mk:
                market[mk[0]] += 1
    total = sum(ops.values())
    if not total:
        return None
    res = {
        "label": label, "total": total,
        "move": sum(v for k, v in ops.items() if k in MOVE) / total,
        "water": ops.get("WATER", 0) / total,
        "plant": ops.get("PLANT", 0) / total,
        "harvest": ops.get("HARVEST", 0) / total,
        "fert": ops.get("FERTILIZE", 0) / total,
        "care": ops.get("CARE", 0) / total,
        "dig": ops.get("DIG", 0) / total,
        "pass": ops.get("PASS", 0) / total,
        "feed": ops.get("FEED", 0) / total,
        "build": (ops.get("BUILD_PASTURE", 0) + ops.get("BUILD_COOP", 0)) / total,
        "ops": ops, "market": market,
    }
    return res


rows = []
# 我们的 agent：用固定动作表形式不方便，改用 op_stats 思路直接从模块跑一局
out = ["高 rating 回放 agent 的行为画像（从官方回放直接提取的动作表）", ""]
for path in sorted(glob.glob("opponents_src/top/top_*.py")):
    name = os.path.basename(path).replace(".py", "")
    r = profile(path, name, out)
    if r:
        rows.append(r)

hdr = (f"{'agent':<24} {'动作数':>7} {'移动':>6} {'浇水':>6} {'种植':>6} "
       f"{'收获':>6} {'施肥':>6} {'照料':>6} {'挖草':>6} {'PASS':>6}")
out.append(hdr)
out.append("-" * len(hdr))
for r in rows:
    out.append(f"{r['label']:<24} {r['total']:>7,} {r['move']:>6.1%} {r['water']:>6.1%} "
               f"{r['plant']:>6.1%} {r['harvest']:>6.1%} {r['fert']:>6.1%} "
               f"{r['care']:>6.1%} {r['dig']:>6.1%} {r['pass']:>6.1%}")

out.append("")
out.append("平均：")
if rows:
    n = len(rows)
    for k in ("move", "water", "plant", "harvest", "fert", "care", "dig", "pass"):
        out.append(f"  {k:<8} {sum(r[k] for r in rows)/n:>6.1%}")

out.append("")
out.append("=== 市场订单构成 ===")
for r in rows:
    top = ", ".join(f"{k}×{v}" for k, v in r["market"].most_common(8))
    out.append(f"{r['label']:<24} {top}")

out.append("")
out.append("=== 平均市场订单构成 ===")
agg = Counter()
for r in rows:
    for k, v in r["market"].items():
        agg[k] += v
for k, v in agg.most_common():
    out.append(f"  {k:<14} {v/max(len(rows),1):>8.1f} 次/局")

text = "\n".join(out)
with open("_docx/top_profiles.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
