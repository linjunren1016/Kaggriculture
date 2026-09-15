"""
量化 V38 与「9 月 meta 配方」的差距（同一口径）。

9 月 rating>=2500 的中位配方（来自官方 episode_features，5652 条记录）：
  草莓 33 · 小麦 164 · 甜瓜 12 · 胡萝卜 31 · 番茄 0 · 总种植 240 · 雇工 12
  收敛度极高：草莓 33 占 80%、甜瓜 12 占 98%、雇工 12 占 79%

这里用同样的定义在本地测 V38，看差多少。
注意：官方数据是**整季累计种植数**（tiles_planted 的语义需按同法统计），
所以本地也按整局累计 PLANT 次数统计，保持一致。
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

TARGET = {"straw": 33, "wheat": 164, "melon": 12, "carrot": 31,
          "tomato": 0, "tiles": 240, "crew": 12}


def profile(path, seeds, label, out):
    fn = get_last_callable(open(path, encoding="utf-8").read(), path=path)
    acc = Counter()
    peaks = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([fn, "pass"])
        planted = Counter()
        peak = 0
        for st in env.steps:
            obs = st[0].observation
            farm = obs["farms"][0]
            peak = max(peak, 1 + len(farm.get("hands", []) or []))
            a = st[0].action or {}
            for op in [a.get("farmer")] + list(a.get("hands") or []):
                if isinstance(op, list) and len(op) >= 2 and op[0] == "PLANT":
                    planted[op[1]] += 1
        acc["straw"] += planted.get("STRAWBERRY", 0)
        acc["wheat"] += planted.get("WHEAT", 0)
        acc["melon"] += planted.get("MELON", 0)
        acc["carrot"] += planted.get("CARROT", 0)
        acc["tomato"] += planted.get("TOMATO", 0)
        acc["tiles"] += sum(planted.values())
        peaks.append(peak)
    n = len(seeds)
    out.append(f"--- {label} ---")
    out.append(f"  {'特征':<10} {'V38':>10} {'9月meta':>10} {'差':>10} {'比值':>8}")
    for k in ("straw", "wheat", "melon", "carrot", "tomato", "tiles"):
        v = acc[k] / n
        t = TARGET[k]
        ratio = (v / t) if t else float("inf")
        out.append(f"  {k:<10} {v:>10.1f} {t:>10} {v-t:>+10.1f} {ratio:>8.2f}")
    out.append(f"  {'crew':<10} {statistics.mean(peaks):>10.1f} {TARGET['crew']:>10} "
               f"{statistics.mean(peaks)-TARGET['crew']:>+10.1f}")


SEEDS = [1400000, 1400001, 1400002, 1400003]
out = ["V38 与 9 月 meta 配方的差距（同口径：整局累计种植数）", ""]
profile("candidates/V38.py", SEEDS, "V38", out)
out.append("")
profile("candidates/C94.py", SEEDS, "C94", out)

text = "\n".join(out)
with open("_docx/gap_vs_meta.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
