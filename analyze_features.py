"""
分析官方对局数据集：高技能分（rating_after）的 agent 在行为特征上有什么不同。

数据来源：Kaggle 官方公开数据集 georgymamarin/kaggriculture-episodes
  agents.csv           每 agent 每局的 final_bank + rating_after
  episode_features.csv 从回放解析的行为特征（雇工、土地、作物、价格）

目标：找出与高评分相关的特征，作为改进方向的依据（而不是靠猜）。
"""
import csv
import statistics
from collections import defaultdict

BASE = "episodes"

# 读 agents.csv 拿 rating
ratings = {}
with open(f"{BASE}/agents.csv", encoding="utf-8-sig", newline="") as fh:
    r = csv.DictReader(fh)
    for row in r:
        try:
            ratings[(row["episode_id"], row["agent_index"])] = float(row["rating_after"])
        except (ValueError, KeyError):
            pass
print(f"ratings: {len(ratings):,}")

# 读 features，并关联 rating
FEATS = ["peak_crew", "total_hires", "first_land_day", "elbow_day",
         "tiles_planted", "plants_carrot", "plants_melon", "plants_strawberry",
         "plants_tomato", "plants_wheat"]
NUM = FEATS + ["final_money"]

buckets = [(0, 600), (600, 800), (800, 1000), (1000, 1200), (1200, 1500),
           (1500, 2000), (2000, 2500), (2500, 3000), (3000, 9999)]
agg = {b: defaultdict(list) for b in buckets}
n_seen = 0
n_rel = 0

with open(f"{BASE}/episode_features.csv", encoding="utf-8-sig", newline="") as fh:
    r = csv.DictReader(fh)
    for row in r:
        n_seen += 1
        key = (row["episode_id"], row["seat"])
        rating = ratings.get(key)
        if rating is None:
            continue
        n_rel += 1
        for b in buckets:
            if b[0] <= rating < b[1]:
                for f in NUM:
                    v = row.get(f)
                    if v in (None, "", "None"):
                        continue
                    try:
                        agg[b][f].append(float(v))
                    except ValueError:
                        pass
                break

out = [f"agents 记录 {len(ratings):,}   features 行 {n_seen:,}   成功关联 {n_rel:,}", ""]
out.append("按 rating_after 分档的行为特征均值")
out.append("")

hdr = f"{'分档':>12} {'样本':>7} " + " ".join(f"{f:>13}" for f in FEATS[:6])
out.append(hdr)
out.append("-" * len(hdr))
for b in buckets:
    d = agg[b]
    n = len(d.get("peak_crew", []))
    if n < 30:
        continue
    vals = " ".join(f"{statistics.mean(d[f]):>13.2f}" if d.get(f) else f"{'-':>13}"
                    for f in FEATS[:6])
    out.append(f"{f'{b[0]}-{b[1]}':>12} {n:>7,} {vals}")

out.append("")
hdr2 = f"{'分档':>12} {'样本':>7} " + " ".join(f"{f:>13}" for f in FEATS[6:])
out.append(hdr2)
out.append("-" * len(hdr2))
for b in buckets:
    d = agg[b]
    n = len(d.get("peak_crew", []))
    if n < 30:
        continue
    vals = " ".join(f"{statistics.mean(d[f]):>13.2f}" if d.get(f) else f"{'-':>13}"
                    for f in FEATS[6:])
    out.append(f"{f'{b[0]}-{b[1]}':>12} {n:>7,} {vals}")

# 最高分档 vs 最低分档 的对比
out.append("")
lo = agg[(600, 800)]
hi = agg[(2500, 3000)]
if lo.get("peak_crew") and hi.get("peak_crew"):
    out.append("=== 高分档(2500-3000) vs 低分档(600-800) ===")
    for f in NUM:
        if lo.get(f) and hi.get(f):
            a, b2 = statistics.mean(lo[f]), statistics.mean(hi[f])
            out.append(f"  {f:<18} 低 {a:>12,.2f}   高 {b2:>12,.2f}   差 {b2-a:>+12,.2f}")

text = "\n".join(out)
with open("_docx/feature_analysis.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
