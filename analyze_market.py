"""
分析官方数据的市场维度：高分 agent 的成交价是否更高。

episode_features.csv 给出每局每个商品的 price_min / price_max。
若高分档的价格区间更高，说明差距在市场层（卖得更贵），而不是农场层。
"""
import csv
import statistics
from collections import defaultdict

PRODUCTS = ["carrot", "egg", "fertilizer", "melon", "milk",
            "strawberry", "tomato", "wheat", "wool"]
BASE = {"wheat": 25, "carrot": 35, "tomato": 60, "strawberry": 120,
        "melon": 250, "egg": 50, "milk": 160, "wool": 200, "fertilizer": 100}

# 读 agents.csv 拿 rating
ratings = {}
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        try:
            ratings[(row["episode_id"], row["agent_index"])] = float(row["rating_after"])
        except (ValueError, KeyError):
            pass

BUCKETS = [(0, 800), (800, 1200), (1200, 1600), (1600, 2000),
           (2000, 2500), (2500, 3000), (3000, 9999)]
agg = {b: defaultdict(list) for b in BUCKETS}
also = {b: defaultdict(list) for b in BUCKETS}

with open("episodes/episode_features.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        rat = ratings.get((row["episode_id"], row["seat"]))
        if rat is None:
            continue
        for b in BUCKETS:
            if b[0] <= rat < b[1]:
                for p in PRODUCTS:
                    for side in ("min", "max"):
                        key = f"price_{p}_{side}"
                        v = row.get(key)
                        if v not in (None, "", "None"):
                            try:
                                agg[b][key].append(float(v))
                            except ValueError:
                                pass
                fm = row.get("final_money")
                if fm not in (None, "", "None"):
                    try:
                        also[b]["final_money"].append(float(fm))
                    except ValueError:
                        pass
                break

out = ["市场维度：各分档的商品价格区间（官方 episodes 数据）", ""]
out.append("每格是「该档的平均 price_max / 基础价」，>1 表示卖在基础价之上")
out.append("")
hdr = f"{'分档':>12} {'样本':>8} " + " ".join(f"{p[:5]:>8}" for p in PRODUCTS)
out.append(hdr)
out.append("-" * len(hdr))
for b in BUCKETS:
    d = agg[b]
    n = len(also[b].get("final_money", []))
    if n < 50:
        continue
    cells = []
    for p in PRODUCTS:
        mx = d.get(f"price_{p}_max")
        cells.append(f"{statistics.mean(mx)/BASE[p]:>8.2f}" if mx else f"{'-':>8}")
    out.append(f"{f'{b[0]}-{b[1]}':>12} {n:>8,} " + " ".join(cells))

out.append("")
out.append("平均 price_max（绝对价格）")
out.append("")
out.append(hdr)
out.append("-" * len(hdr))
for b in BUCKETS:
    d = agg[b]
    n = len(also[b].get("final_money", []))
    if n < 50:
        continue
    cells = []
    for p in PRODUCTS:
        mx = d.get(f"price_{p}_max")
        cells.append(f"{statistics.mean(mx):>8.0f}" if mx else f"{'-':>8}")
    out.append(f"{f'{b[0]}-{b[1]}':>12} {n:>8,} " + " ".join(cells))

out.append("")
out.append("各档终局资金均值")
for b in BUCKETS:
    v = also[b].get("final_money")
    if v and len(v) >= 50:
        out.append(f"  {b[0]}-{b[1]}: {statistics.mean(v):>12,.0f}  (n={len(v):,})")

# 高分 vs 低分 的价格比
out.append("")
lo, hi = agg[(0, 800)], agg[(2500, 3000)]
if lo.get("price_wheat_max") and hi.get("price_wheat_max"):
    out.append("=== 2500-3000 档 相对 0-800 档的 price_max 倍数 ===")
    for p in PRODUCTS:
        a, b2 = lo.get(f"price_{p}_max"), hi.get(f"price_{p}_max")
        if a and b2:
            ma, mb = statistics.mean(a), statistics.mean(b2)
            out.append(f"  {p:<12} 低 {ma:>8.1f}   高 {mb:>8.1f}   倍数 {mb/ma:>6.2f}x")

text = "\n".join(out)
with open("_docx/market_analysis.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
