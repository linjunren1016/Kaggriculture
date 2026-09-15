"""
按「众数农场」筛出近期顶尖回放，作为候选骨架。

依据（来自 what-the-top-farms-do）：
  3100 分段的 modal farm（8-10/8-11）= 9 牛 + 4 羊 · 1 小麦 · 10 雇工 · NE+NW+SW
  旧的 8c6s 已被替代；草莓是晚期主力；施肥是免费钱。

做法：
  1. 从 episode_features 找 9 月、高 rating、且作物以草莓+小麦为主的局
  2. 从 agents.csv 找这些局的 agent 与其 rating
  3. 输出目标清单（episode_id, seat），供回放提取
"""
import csv
from collections import defaultdict

# 1) 9 月 PUBLIC 局的时间
ep_time = {}
with open("episodes/episodes.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        ep_time[row["episode_id"]] = (row.get("create_time", ""), row.get("type", ""))

# 2) rating
ratings = {}
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        try:
            ratings[(row["episode_id"], row["agent_index"])] = float(row["rating_after"])
        except (ValueError, KeyError):
            pass

# 3) features：找草莓为主、评级高的 9 月局
cands = []
with open("episodes/episode_features.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        eid = row["episode_id"]
        ct, ty = ep_time.get(eid, ("", ""))
        if not ct.startswith("2026-09") or "PUBLIC" not in ty:
            continue
        seat = row["seat"]
        r = ratings.get((eid, seat))
        if r is None or r < 2600:
            continue
        def g(k):
            v = row.get(k)
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0
        straw = g("plants_strawberry")
        wheat = g("plants_wheat")
        melon = g("plants_melon")
        carrot = g("plants_carrot")
        tomato = g("plants_tomato")
        tiles = g("tiles_planted")
        crew = g("peak_crew")
        # 骨架特征：草莓 25-45、小麦 5-40、番茄极少、胡萝卜极少
        if not (25 <= straw <= 45):
            continue
        if tomato > 3 or carrot > 15:
            continue
        if wheat > 60:
            continue
        cands.append({
            "eid": eid, "seat": seat, "rating": r, "ct": ct,
            "straw": straw, "wheat": wheat, "melon": melon,
            "carrot": carrot, "tomato": tomato,
            "tiles": tiles, "crew": crew,
            "min_day": g("first_land_day"),
        })

cands.sort(key=lambda c: -c["rating"])
out = [f"符合「草莓为主骨架」的 9 月高 rating 局（>=2600）: {len(cands)} 条", ""]
out.append(f"{'episode':>10} {'seat':>5} {'rating':>9} {'草莓':>5} {'小麦':>5} "
           f"{'甜瓜':>5} {'胡萝卜':>6} {'番茄':>5} {'种植':>5} {'雇工':>5}  create_time")
for c in cands[:30]:
    out.append(f"{c['eid']:>10} {c['seat']:>5} {c['rating']:>9,.1f} {c['straw']:>5.0f} "
               f"{c['wheat']:>5.0f} {c['melon']:>5.0f} {c['carrot']:>6.0f} "
               f"{c['tomato']:>5.0f} {c['tiles']:>5.0f} {c['crew']:>5.0f}  {c['ct'][:19]}")

# 统计骨架共识
import statistics
if cands:
    out.append("")
    out.append("该子集均值：")
    for k in ("straw", "wheat", "melon", "carrot", "tomato", "tiles", "crew", "min_day"):
        out.append(f"  {k:<9} {statistics.mean(c[k] for c in cands):>7.1f}")

# 写目标清单
lines = [f"{c['eid']},{c['seat']},{c['rating']:.1f},0" for c in cands[:12]]
with open("_docx/modal_targets.csv", "w", encoding="utf-8") as fh:
    fh.write("episode_id,seat,rating,bank\n")
    fh.write("\n".join(lines))

text = "\n".join(out)
with open("_docx/modal_targets.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
