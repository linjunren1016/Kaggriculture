"""
meta_line 参考 agent 之间的循环赛：选出互相对打最强者。

为什么需要这一步
----------------
manifest 里的"预期资金"是各 agent 对**内置 starter** 测出来的，不是互相对打的强度。
要选一个采用，必须看它们**彼此**对打谁赢。

四个候选（MIT 许可，明确允许用于构建提交）：
  broker_bea / ledger_lena / slotter_silas / closer_cleo

用法：
    python meta_roundrobin.py --episodes 2 --seed-base 50000
"""
import argparse
import contextlib
import io
import itertools
import os
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")

META = ["broker_bea.py", "ledger_lena.py", "slotter_silas.py", "closer_cleo.py"]
BASE = "opponents_src"


def load(name):
    path = os.path.join(BASE, name)
    raw = open(path, encoding="utf-8").read()
    return get_last_callable(raw, path=path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=2)
    ap.add_argument("--seed-base", type=int, default=50000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    seeds = [args.seed_base + i for i in range(args.episodes)]
    agents = {n: load(n) for n in META}

    wins = {n: 0 for n in META}
    losses = {n: 0 for n in META}
    margins = {n: [] for n in META}
    money = {n: [] for n in META}
    lines = [f"meta_line 循环赛（{len(seeds)} 种子 × 双座位 × {len(META)} 组合）", ""]

    for a, b in itertools.combinations(META, 2):
        for seed in seeds:
            for order in (0, 1):
                env = make("kaggriculture",
                           configuration={"episodeSteps": args.steps, "seed": seed},
                           debug=False)
                env.run([agents[a], agents[b]] if order == 0 else [agents[b], agents[a]])
                f = env.steps[-1]
                ma, mb = float(f[0].reward or 0), float(f[1].reward or 0)
                if order == 1:
                    ma, mb = mb, ma
                if f[0].status != "DONE":
                    continue
                money[a].append(ma)
                money[b].append(mb)
                margins[a].append(ma - mb)
                margins[b].append(mb - ma)
                if ma > mb:
                    wins[a] += 1
                    losses[b] += 1
                elif mb > ma:
                    wins[b] += 1
                    losses[a] += 1

    lines.append(f"{'agent':<20} {'战绩':>10} {'胜率':>7} {'平均资金':>11} {'平均分差':>11}")
    lines.append("-" * 64)
    ranking = []
    for n in META:
        tot = wins[n] + losses[n]
        wr = wins[n] / tot if tot else 0
        ranking.append((n, wr, statistics.mean(money[n]) if money[n] else 0))
        lines.append(f"{n:<20} {f'{wins[n]}W-{losses[n]}L':>10} {wr:>7.0%} "
                     f"{statistics.mean(money[n]) if money[n] else 0:>11,.0f} "
                     f"{statistics.mean(margins[n]) if margins[n] else 0:>+11,.0f}")

    ranking.sort(key=lambda r: (-r[1], -r[2]))
    lines.append("")
    lines.append("按互相对战胜率排序：")
    for i, (n, wr, m) in enumerate(ranking, 1):
        lines.append(f"  {i}. {n:<20} 胜率 {wr:.0%}   平均资金 {m:,.0f}")

    text = "\n".join(lines)
    with open("_docx/meta_rr.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
