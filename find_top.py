"""
定位最高 rating 的提交与其对局，准备从回放重建其动作序列。

注意：数据只覆盖有回放的对局（按 README 是偏向最活跃提交的采样），
所以这里的"最高"是「在已存回放中出现的最高」。
"""
import csv
from collections import defaultdict

# 1) 每个提交的 rating 峰值
peak = {}
games = defaultdict(int)
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        sid = row["submission_id"]
        try:
            r = float(row["rating_after"])
        except (ValueError, KeyError):
            continue
        games[sid] += 1
        if r > peak.get(sid, -1e9):
            peak[sid] = r

out = [f"提交数 {len(peak):,}", ""]
top = sorted(peak.items(), key=lambda kv: -kv[1])[:25]
out.append(f"{'submission_id':>16} {'峰值rating':>11} {'回放局数':>9}")
for sid, r in top:
    out.append(f"{sid:>16} {r:>11,.1f} {games[sid]:>9,}")

# 2) 找出这些提交参与的对局 id 及其在该局的 rating / bank
targets = {sid for sid, _ in top}
ep_of = defaultdict(list)
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        sid = row["submission_id"]
        if sid in targets:
            try:
                ep_of[sid].append((row["episode_id"], int(row["agent_index"]),
                                   float(row["rating_after"]), float(row["final_bank"])))
            except (ValueError, KeyError):
                continue

out.append("")
out.append("=== 各提交在其最高 rating 那一局的详情 ===")
TOPKEEP = {}
for sid, r in top:
    rows = ep_of.get(sid, [])
    if not rows:
        continue
    # 找 rating 最接近峰值的那局
    best = min(rows, key=lambda t: abs(t[2] - r))
    out.append(f"  sub {sid}  峰值 {r:,.1f} → ep {best[0]} seat {best[1]} "
               f"(该局 rating {best[2]:,.1f}, bank {best[3]:,.0f}, 共 {len(rows)} 局)")
    TOPKEEP[sid] = {"episode_id": best[0], "seat": best[1],
                    "rating": best[2], "bank": best[3], "peak": r}

# 3) 也统计：这些高 rating 对局的对手强度
out.append("")
out.append("=== 候选回放清单（episode_id, seat）===")
lines = []
for sid, d in TOPKEEP.items():
    lines.append(f"{d['episode_id']},{d['seat']},{sid},{d['rating']:.1f},{d['bank']:.0f}")
    out.append("  " + lines[-1])

with open("_docx/top_subs.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
with open("_docx/top_targets.csv", "w", encoding="utf-8") as fh:
    fh.write("episode_id,seat,submission_id,rating,bank\n")
    fh.write("\n".join(lines))

print("\n".join(out))
