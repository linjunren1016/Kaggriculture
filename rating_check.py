"""
核实技能分的初始值与分布：从数据里找「某提交最早几局」的 rating_after。

目的：确认初始分是多少、爬升空间有多大。
若初始分是 600，从 600 爬到 3000 需要极多净胜局；
若初始分本来就高（例如 1000+），结论会不同。
"""
import csv
from collections import defaultdict

# 每个 submission 的 rating 序列（按 episode 顺序）
seq = defaultdict(list)
with open("episodes/agents.csv", encoding="utf-8-sig", newline="") as fh:
    for row in csv.DictReader(fh):
        try:
            seq[row["submission_id"]].append((row["episode_id"], float(row["rating_after"])))
        except (ValueError, KeyError):
            continue

out = [f"提交数: {len(seq):,}", ""]

# 每个提交的局数分布
lens = sorted(len(v) for v in seq.values())
n = len(lens)
out.append("每个提交的对局数分布：")
for q, lab in [(0.5, "中位"), (0.9, "p90"), (0.99, "p99"), (0.999, "p99.9")]:
    out.append(f"  {lab:<6} {lens[int(n*q)]:>8,} 局")
out.append(f"  最多   {lens[-1]:>8,} 局")

# 局数最多的几个提交，看它们的 rating 轨迹（首值 -> 末值）
out.append("")
out.append("对局数最多的 15 个提交（首/末 rating）：")
top = sorted(seq.items(), key=lambda kv: -len(kv[1]))[:15]
out.append(f"{'submission_id':>16} {'局数':>8} {'首个rating':>11} {'末个rating':>11} {'最高':>9}")
for sid, v in top:
    vals = [r for _, r in v]
    out.append(f"{sid:>16} {len(v):>8,} {vals[0]:>11,.1f} {vals[-1]:>11,.1f} {max(vals):>9,.1f}")

# 全局：所有 rating 的最小/最大/分位
allr = sorted(r for v in seq.values() for _, r in v)
out.append("")
out.append(f"全部 rating_after: n={len(allr):,}")
for q, lab in [(0.01, "p1"), (0.10, "p10"), (0.25, "p25"), (0.50, "中位"),
               (0.75, "p75"), (0.90, "p90"), (0.99, "p99"), (0.999, "p99.9")]:
    out.append(f"  {lab:<6} {allr[int(len(allr)*q)]:>10,.1f}")
out.append(f"  最低   {allr[0]:>10,.1f}")
out.append(f"  最高   {allr[-1]:>10,.1f}")

# 每个提交只取"最终 rating"（末值），看分布
finals = sorted(v[-1][1] for v in seq.values())
out.append("")
out.append("各提交「最终 rating」分布：")
for q, lab in [(0.25, "p25"), (0.50, "中位"), (0.75, "p75"),
               (0.90, "p90"), (0.99, "p99")]:
    out.append(f"  {lab:<6} {finals[int(len(finals)*q)]:>10,.1f}")
out.append(f"  最高   {finals[-1]:>10,.1f}")

text = "\n".join(out)
with open("_docx/rating_check.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
