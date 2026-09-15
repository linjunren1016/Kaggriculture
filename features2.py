"""
挖官方 episode_features 里尚未分析的列，按 rating 分档对比。

此前只看了作物/牲畜/雇工。这里聚焦三个尚未分析的时点/规模特征：
  first_land_day : 首次买地的天（扩张时机）
  elbow_day      : 资金首次达到终局 10% 的天（起势快慢）
  peak_crew      : 峰值雇工
并统计引擎版本切换（1.32.7 于 8/15 上线）前后的差异。
"""
import csv
import statistics
from collections import defaultdict

ratings = {}
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        try:
            ratings[(row["episode_id"], row["agent_index"])] = float(row["rating_after"])
        except (ValueError, KeyError):
            pass

BUCKETS = [(0, 800), (800, 1200), (1200, 1600), (1600, 2000),
           (2000, 2500), (2500, 2800), (2800, 9999)]
NUM = ["first_land_day", "elbow_day", "peak_crew", "total_hires",
       "tiles_planted", "final_money"]

agg = {b: defaultdict(list) for b in BUCKETS}
byver = defaultdict(lambda: defaultdict(list))

with open("episodes/episode_features.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        rat = ratings.get((row["episode_id"], row["seat"]))
        if rat is None:
            continue
        for b in BUCKETS:
            if b[0] <= rat < b[1]:
                for f in NUM:
                    v = row.get(f)
                    if v not in (None, "", "None"):
                        try:
                            agg[b][f].append(float(v))
                        except ValueError:
                            pass
                ev = row.get("engine_version") or "?"
                for f in NUM:
                    v = row.get(f)
                    if v not in (None, "", "None"):
                        try:
                            byver[ev][f].append(float(v))
                        except ValueError:
                            pass
                break

out = ["按 rating 分档：时点与规模特征", ""]
hdr = f"{'分档':>12} {'样本':>8} " + " ".join(f"{f:>14}" for f in NUM)
out.append(hdr)
out.append("-" * len(hdr))
for b in BUCKETS:
    d = agg[b]
    n = len(d.get("peak_crew", []))
    if n < 50:
        continue
    cells = []
    for f in NUM:
        cells.append(f"{statistics.mean(d[f]):>14,.2f}" if d.get(f) else f"{'-':>14}")
    out.append(f"{f'{b[0]}-{b[1]}':>12} {n:>8,} " + " ".join(cells))

out.append("")
out.append("=== 引擎版本对比（1.32.7 于 8/15 上线）===")
out.append(f"{'版本':>12} {'样本':>9} " + " ".join(f"{f:>13}" for f in NUM[:4]))
out.append("-" * 74)
for ev in sorted(byver):
    d = byver[ev]
    n = len(d.get("peak_crew", []))
    if n < 100:
        continue
    cells = []
    for f in NUM[:4]:
        cells.append(f"{statistics.mean(d[f]):>13,.2f}" if d.get(f) else f"{'-':>13}")
    out.append(f"{ev:>12} {n:>9,} " + " ".join(cells))

# 最高档 vs 最低档的差异
out.append("")
lo, hi = agg[(0, 800)], agg[(2800, 9999)]
if lo.get("peak_crew") and hi.get("peak_crew"):
    out.append("=== 2800+ 档 vs 0-800 档 ===")
    for f in NUM:
        if lo.get(f) and hi.get(f):
            a, b2 = statistics.mean(lo[f]), statistics.mean(hi[f])
            out.append(f"  {f:<16} 低 {a:>12,.2f}   高 {b2:>12,.2f}   差 {b2-a:>+12,.2f}")

text = "\n".join(out)
with open("_docx/features2.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
