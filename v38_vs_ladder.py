"""
V38 对天梯各层的胜率（严格协议：多种子、双座位、逐局记账）。

目的：确认 V38 相对参考天梯的真实位置。
若 V38 明显强于 tier7-9，则"我们方案弱导致分数低"的解释不成立，
分数差距更可能来自评分机制（成熟度/匹配）而非方案实力。
"""
import argparse
import contextlib
import io
import os
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")

LADDER = [
    ("tier5 Rancher Rita", "opponents_src/rancher_rita.py"),
    ("tier6 Broker Bea", "opponents_src/broker_bea.py"),
    ("tier7 Ledger Lena", "opponents_src/ledger_lena.py"),
    ("tier8 Slotter Silas", "opponents_src/slotter_silas.py"),
    ("tier9 Closer Cleo", "opponents_src/closer_cleo.py"),
]


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


ap = argparse.ArgumentParser()
ap.add_argument("--agent", default="candidates/V38.py")
ap.add_argument("--episodes", type=int, default=10)
ap.add_argument("--seed-base", type=int, default=930000)
args = ap.parse_args()

mine = load(args.agent)
seeds = [args.seed_base + i for i in range(args.episodes)]
out = [f"{os.path.basename(args.agent)} 对天梯（{len(seeds)} 种子 × 双座位 = "
       f"{len(seeds)*2} 局/对手）", ""]
out.append(f"{'对手':<20} {'战绩':>12} {'胜率':>7} {'我方均资金':>12} {'对手均资金':>12}")
out.append("-" * 68)

tot_w = tot_n = 0
for label, path in LADDER:
    if not os.path.exists(path):
        out.append(f"{label:<20} (文件缺失)")
        continue
    opp = load(path)
    rows = []
    for seed in seeds:
        for mine_seat in (0, 1):
            first, second = (mine, opp) if mine_seat == 0 else (opp, mine)
            env = make("kaggriculture",
                       configuration={"episodeSteps": 720, "seed": seed}, debug=False)
            env.run([first, second])
            f = env.steps[-1]
            if f[0].status != "DONE" or f[1].status != "DONE":
                continue
            m0, m1 = float(f[0].reward or 0), float(f[1].reward or 0)
            mm, mo = (m0, m1) if mine_seat == 0 else (m1, m0)
            rows.append((mm, mo))
    if not rows:
        out.append(f"{label:<20} (无有效对局)")
        continue
    w = sum(1 for a, b in rows if a > b)
    tot_w += w
    tot_n += len(rows)
    out.append(f"{label:<20} {f'{w}W-{len(rows)-w}L':>12} {w/len(rows):>7.0%} "
               f"{statistics.mean(a for a,_ in rows):>12,.0f} "
               f"{statistics.mean(b for _,b in rows):>12,.0f}")

out.append("")
out.append(f"合计 {tot_w}W-{tot_n-tot_w}L   总胜率 {tot_w/tot_n:.1%}" if tot_n else "无数据")

text = "\n".join(out)
with open("_docx/v38_vs_ladder.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
