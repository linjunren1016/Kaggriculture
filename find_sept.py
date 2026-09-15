"""
筛出 9 月的高 rating 对局（用于提取当前 meta 的回放）。

与 8 月那批不同，这里限定 episode 的 create_time 在 9 月，
因此反映的是**当前** meta 而不是一个月前的。

只读 CSV，不碰 parquet，输出目标清单供后续提取。
"""
import csv
from collections import defaultdict

# 1) episode -> create_time / type
ep_time = {}
with open("episodes/episodes.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        ep_time[row["episode_id"]] = (row.get("create_time", ""), row.get("type", ""))

# 2) agent -> rating / bank / seat，按 9 月 + PUBLIC 过滤
cands = defaultdict(list)
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        eid = row["episode_id"]
        ct, ty = ep_time.get(eid, ("", ""))
        if not ct.startswith("2026-09"):
            continue
        if "PUBLIC" not in ty:
            continue
        try:
            r = float(row["rating_after"])
            b = float(row["final_bank"])
        except (ValueError, KeyError):
            continue
        cands[row["submission_id"]].append((eid, row["agent_index"], r, b, ct))

out = [f"9 月 PUBLIC 对局中出现的提交数: {len(cands):,}", ""]

# 每个提交在 9 月的最高 rating 那一局
best = {}
for sid, rows in cands.items():
    top = max(rows, key=lambda t: t[2])
    best[sid] = top

ranked = sorted(best.items(), key=lambda kv: -kv[1][2])[:30]
out.append(f"{'submission':>12} {'rating':>9} {'bank':>10} {'episode':>10} {'seat':>5}  create_time")
out.append("-" * 78)
lines = []
for sid, (eid, seat, r, b, ct) in ranked:
    out.append(f"{sid:>12} {r:>9,.1f} {b:>10,.0f} {eid:>10} {seat:>5}  {ct[:19]}")
    lines.append(f"{eid},{seat},{sid},{r:.1f},{b:.0f}")

# 也统计 9 月 rating 分布
allr = sorted(v[2] for v in best.values())
n = len(allr)
out.append("")
out.append(f"9 月各提交最高 rating 分布 (n={n:,})：")
for q, lab in [(0.50, "中位"), (0.75, "p75"), (0.90, "p90"), (0.95, "p95"), (0.99, "p99")]:
    out.append(f"  {lab:<6} {allr[int(n*q)]:>9,.1f}")
out.append(f"  最高   {allr[-1]:>9,.1f}")

# 时间上最新的高分（限定 9/10 之后）
recent = [(sid, v) for sid, v in best.items() if v[4] >= "2026-09-10"]
recent.sort(key=lambda kv: -kv[1][2])
out.append("")
out.append(f"9/10 之后的高分提交（前 20，n={len(recent)}）：")
lines2 = []
for sid, (eid, seat, r, b, ct) in recent[:20]:
    out.append(f"  {sid:>12} {r:>9,.1f} {b:>10,.0f} {eid:>10} seat{seat}  {ct[:19]}")
    lines2.append(f"{eid},{seat},{sid},{r:.1f},{b:.0f}")

with open("_docx/sept_targets.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
with open("_docx/sept_targets.csv", "w", encoding="utf-8") as fh:
    fh.write("episode_id,seat,submission_id,rating,bank\n")
    fh.write("\n".join(lines2 or lines))

print("\n".join(out))
