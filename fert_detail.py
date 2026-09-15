"""
核实：9 月高分 agent 的 FERTILIZE 用得多不多，以及是否与牲畜规模相关。

方法：从已还原的 9 月 agent 动作表里统计 FERTILIZE 出现的位置，
并统计 BUILD_PASTURE / BUY_ANIMAL，判断它们是"作物施肥"还是"收牲畜肥料"。
"""
import glob
import importlib.util
import os
from collections import Counter

out = ["9 月高分 agent 的动作细节（来自还原的动作表）", ""]
out.append(f"{'episode':>10} {'rating':>9} {'FERT':>6} {'COLLECT':>8} "
           f"{'BUILD_P':>8} {'BUY_AN':>7} {'CARE':>6} {'SELL':>5} {'BUY_SEED':>9}")

for path in sorted(glob.glob("opponents_src/sept/sept_*.py")):
    spec = importlib.util.spec_from_file_location("m", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    table = getattr(m, "_TABLE", {})
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
    name = os.path.basename(path).replace(".py", "")
    eid = name.split("_")[1]
    out.append(f"{eid:>10} {'?':>9} {ops.get('FERTILIZE',0):>6} "
               f"{ops.get('COLLECT_FERTILIZER',0):>8} "
               f"{ops.get('BUILD_PASTURE',0):>8} "
               f"{market.get('BUY_ANIMAL',0):>7} "
               f"{ops.get('CARE',0):>6} {market.get('SELL',0):>5} "
               f"{market.get('BUY_SEED',0):>9}")

text = "\n".join(out)
with open("_docx/fert_detail.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
