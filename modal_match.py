"""
查已提取的 9 月高分 agent 是否符合「9 月 meta 配方」。

配方（rating>=2500 中位）：草莓 33 · 小麦 164 · 甜瓜 12 · 胡萝卜 31 · 总种植 240 · 雇工 12
若其中某个本来就是这个配方，它的动作表就是最好的候选基座。
"""
import csv

# 9 月目标的 features
targets = {}
with open("_docx/sept_targets.csv", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        targets[(row["episode_id"], row["seat"])] = float(row["rating"])

out = ["已提取的 9 月 agent 是否符合 meta 配方", ""]
out.append(f"{'episode':>10} {'seat':>5} {'rating':>9} {'草莓':>5} {'小麦':>5} "
           f"{'甜瓜':>5} {'胡萝卜':>6} {'番茄':>5} {'种植':>6} {'雇工':>5}  匹配度")
out.append("-" * 90)

# 目标配方
T = {"plants_strawberry": 33, "plants_wheat": 164, "plants_melon": 12,
     "plants_carrot": 31, "plants_tomato": 0, "tiles_planted": 240, "peak_crew": 12}

rows = []
with open("episodes/episode_features.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        key = (row["episode_id"], row["seat"])
        if key not in targets:
            continue

        def g(k):
            try:
                return float(row.get(k) or 0)
            except (TypeError, ValueError):
                return 0.0
        vals = {k: g(k) for k in T}
        # 匹配度：各特征相对偏差的均值（越小越像）
        devs = []
        for k, tv in T.items():
            v = vals[k]
            devs.append(abs(v - tv) / (tv if tv else 1))
        score = sum(devs) / len(devs)
        rows.append((row["episode_id"], row["seat"], targets[key], vals, score))

for eid, seat, rating, v, score in sorted(rows, key=lambda r: r[4]):
    out.append(f"{eid:>10} {seat:>5} {rating:>9,.1f} {v['plants_strawberry']:>5.0f} "
               f"{v['plants_wheat']:>5.0f} {v['plants_melon']:>5.0f} "
               f"{v['plants_carrot']:>6.0f} {v['plants_tomato']:>5.0f} "
               f"{v['tiles_planted']:>6.0f} {v['peak_crew']:>5.0f}  {score:>7.3f}")

out.append("")
out.append(f"（匹配度 = 各特征相对偏差的均值，0 = 完全符合配方）")
if rows:
    best = min(rows, key=lambda r: r[4])
    out.append(f"最接近配方的是 ep {best[0]} seat {best[1]}（匹配度 {best[4]:.3f}）")

text = "\n".join(out)
with open("_docx/modal_match.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
