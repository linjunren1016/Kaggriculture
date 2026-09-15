"""看 9 月高 rating agent 的作物分布，据此确定"骨架"筛选条件。"""
import csv
import statistics
from collections import Counter

ep_time = {}
with open("episodes/episodes.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        ep_time[row["episode_id"]] = (row.get("create_time", ""), row.get("type", ""))

ratings = {}
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        try:
            ratings[(row["episode_id"], row["agent_index"])] = float(row["rating_after"])
        except (ValueError, KeyError):
            pass

rows = []
with open("episodes/episode_features.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        eid = row["episode_id"]
        ct, ty = ep_time.get(eid, ("", ""))
        if not ct.startswith("2026-09") or "PUBLIC" not in ty:
            continue
        r = ratings.get((eid, row["seat"]))
        if r is None or r < 2500:
            continue

        def g(k):
            try:
                return float(row.get(k) or 0)
            except (TypeError, ValueError):
                return 0.0
        rows.append({
            "eid": eid, "rating": r, "ct": ct,
            "straw": g("plants_strawberry"), "wheat": g("plants_wheat"),
            "melon": g("plants_melon"), "carrot": g("plants_carrot"),
            "tomato": g("plants_tomato"), "tiles": g("tiles_planted"),
            "crew": g("peak_crew"), "land": g("first_land_day"),
            "money": g("final_money"),
        })

out = [f"9 月 rating>=2500 的 agent 记录: {len(rows)} 条", ""]
if rows:
    out.append("=== 各特征分位 ===")
    out.append(f"{'特征':<12} {'p10':>8} {'p25':>8} {'中位':>8} {'p75':>8} {'p90':>8} {'均值':>9}")
    out.append("-" * 62)
    for k in ("straw", "wheat", "melon", "carrot", "tomato", "tiles", "crew", "money"):
        v = sorted(r[k] for r in rows)
        n = len(v)
        q = lambda p: v[min(n - 1, int(n * p))]
        out.append(f"{k:<12} {q(0.10):>8.1f} {q(0.25):>8.1f} {q(0.50):>8.1f} "
                   f"{q(0.75):>8.1f} {q(0.90):>8.1f} {statistics.mean(v):>9.1f}")

    out.append("")
    out.append("=== 各特征的常见取值（取整后 top 8）===")
    for k in ("straw", "wheat", "melon", "carrot", "tomato", "crew"):
        c = Counter(int(round(r[k])) for r in rows)
        out.append(f"  {k:<8} " + ", ".join(f"{v}×{n}" for v, n in c.most_common(8)))

    # 最高分那批的骨架
    hi = sorted(rows, key=lambda r: -r["rating"])[:20]
    out.append("")
    out.append("=== rating 最高的 20 条 ===")
    out.append(f"{'episode':>10} {'rating':>8} {'草莓':>5} {'小麦':>5} {'甜瓜':>5} "
               f"{'胡萝卜':>6} {'番茄':>5} {'种植':>5} {'雇工':>5} {'资金':>9}")
    for r in hi:
        out.append(f"{r['eid']:>10} {r['rating']:>8,.1f} {r['straw']:>5.0f} {r['wheat']:>5.0f} "
                   f"{r['melon']:>5.0f} {r['carrot']:>6.0f} {r['tomato']:>5.0f} "
                   f"{r['tiles']:>5.0f} {r['crew']:>5.0f} {r['money']:>9,.0f}")

text = "\n".join(out)
with open("_docx/sept_dist.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
