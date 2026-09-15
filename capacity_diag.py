"""
诊断 V38 为什么只种 188 格（meta 是 240）。

可能原因：
  A. 劳动力瓶颈：13 个雇工维护不了 240 格
  B. 空地不足：只解锁了 3 象限 = 75 格，但整季轮作需要 240 次种植
  C. 决策问题：有空地但不种

注意口径：官方 tiles_planted 是**整季累计种植次数**（含收获后复种），
所以 240 次 ≠ 240 格。3 象限 75 格里轮作也能累到 240。

本脚本测：
  1. V38 的地块占用曲线（每天有多少格被占）
  2. 空地数（有机会种却没种）
  3. 动作构成（种 vs 浇水 vs 移动）
  4. 如果给更多雇工，能否种更多
"""
import contextlib
import io
import statistics
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")


def diag(path, seeds, label, out):
    fn = get_last_callable(open(path, encoding="utf-8").read(), path=path)
    util, empties, weeds, crops = [], [], [], []
    ops = Counter()
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([fn, "pass"])
        for i, st in enumerate(env.steps):
            if i % 24:            # 每天采样一次
                continue
            farm = st[0].observation["farms"][0]
            tiles = farm["tiles"]
            c = e = w = 0
            for row in tiles:
                for t in row:
                    if t == "LOCKED":
                        continue
                    if isinstance(t, dict):
                        if t.get("kind") == "PLANT":
                            c += 1
                        elif t.get("kind") == "WEED":
                            w += 1
                    elif t is None:
                        e += 1
            crops.append(c)
            empties.append(e)
            weeds.append(w)
            util.append(c / max(c + e + w, 1))
            a = st[0].action or {}
            for op in [a.get("farmer")] + list(a.get("hands") or []):
                if isinstance(op, list) and op:
                    ops[op[0]] += 1
    out.append(f"--- {label} ---")
    out.append(f"  日均作物数 {statistics.mean(crops):>6.1f}   "
               f"空地 {statistics.mean(empties):>6.1f}   "
               f"杂草 {statistics.mean(weeds):>5.1f}")
    out.append(f"  地块占用率 {statistics.mean(util):>6.1%}")
    tot = sum(ops.values()) or 1
    for k in ("PLANT", "WATER", "HARVEST", "DIG", "PASS"):
        out.append(f"  {k:<10} {ops.get(k,0)/tot:>6.1%}  ({ops.get(k,0)})")


SEEDS = [1500000, 1500001, 1500002]
out = ["V38 产能利用率诊断（为何只种 188 / meta 是 240）", ""]
diag("candidates/V38.py", SEEDS, "V38", out)
out.append("")
diag("candidates/C94.py", SEEDS, "C94", out)

text = "\n".join(out)
with open("_docx/capacity.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
