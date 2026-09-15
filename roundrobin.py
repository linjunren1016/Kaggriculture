"""
任意 agent 集合的循环赛（双座位、可指定种子区间）。

用于比较候选提交版：当前提交版 C94、作者后续版 C95、
以及公开的 Kaito V27（从 notebook 提取）。

用法：
    python roundrobin.py --agents opponents_src/C94.py opponents_src/C95.py opponents_src/KaitoV27.py --episodes 8
"""
import argparse
import contextlib
import importlib.util
import io
import itertools
import os
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")


def load(path):
    raw = open(path, encoding="utf-8").read()
    return get_last_callable(raw, path=path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", nargs="+", required=True)
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=200000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    names = [os.path.basename(p).replace(".py", "") for p in args.agents]
    agents = {n: load(p) for n, p in zip(names, args.agents)}
    seeds = [args.seed_base + i for i in range(args.episodes)]

    wins = {n: 0 for n in names}
    losses = {n: 0 for n in names}
    ties = {n: 0 for n in names}
    money = {n: [] for n in names}
    margins = {n: [] for n in names}
    matrix = {a: {b: [0, 0] for b in names} for a in names}

    for a, b in itertools.combinations(names, 2):
        for seed in seeds:
            for order in (0, 1):
                env = make("kaggriculture",
                           configuration={"episodeSteps": args.steps, "seed": seed},
                           debug=False)
                env.run([agents[a], agents[b]] if order == 0 else [agents[b], agents[a]])
                f = env.steps[-1]
                if f[0].status != "DONE" or f[1].status != "DONE":
                    continue
                ma, mb = float(f[0].reward or 0), float(f[1].reward or 0)
                if order == 1:
                    ma, mb = mb, ma
                money[a].append(ma)
                money[b].append(mb)
                margins[a].append(ma - mb)
                margins[b].append(mb - ma)
                if ma > mb:
                    wins[a] += 1
                    losses[b] += 1
                    matrix[a][b][0] += 1
                elif mb > ma:
                    wins[b] += 1
                    losses[a] += 1
                    matrix[b][a][0] += 1
                else:
                    ties[a] += 1
                    ties[b] += 1
                    matrix[a][b][1] += 1

    lines = [f"循环赛：{', '.join(names)}",
             f"种子 {seeds[0]}–{seeds[-1]}（{len(seeds)} 个）× 双座位", ""]
    lines.append(f"{'agent':<22} {'战绩':>12} {'胜率':>7} {'平均资金':>11} {'平均分差':>10}")
    lines.append("-" * 68)
    ranking = []
    for n in names:
        tot = wins[n] + losses[n] + ties[n]
        wr = wins[n] / tot if tot else 0
        ranking.append((n, wr, wins[n], losses[n], ties[n]))
        lines.append(f"{n:<22} {f'{wins[n]}W-{losses[n]}L-{ties[n]}T':>12} {wr:>7.0%} "
                     f"{statistics.mean(money[n]) if money[n] else 0:>11,.0f} "
                     f"{statistics.mean(margins[n]) if margins[n] else 0:>+10,.0f}")

    lines.append("")
    lines.append("两两对战胜负矩阵（行 = 获胜方）：")
    for a in names:
        parts = []
        for b in names:
            if a == b:
                parts.append("—")
                continue
            w, t = matrix[a][b]
            lw, lt = matrix[b][a]
            parts.append(f"{b}:{w}W{t}T")
        lines.append(f"  {a:<22} " + "  ".join(parts))

    ranking.sort(key=lambda r: -r[1])
    lines.append("")
    lines.append("按胜率排序：")
    for i, (n, wr, w, l, t) in enumerate(ranking, 1):
        lines.append(f"  {i}. {n:<22} {wr:.0%}  ({w}W-{l}L-{t}T)")

    text = "\n".join(lines)
    with open("_docx/roundrobin.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
