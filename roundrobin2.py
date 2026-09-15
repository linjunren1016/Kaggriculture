"""
循环赛（重写版）。

修复旧版的问题：旧代码在座位交换时对胜负的记账不自洽，导致胜负矩阵不对称
（例如 A 对 B 记 10 胜，而 B 对 A 只记 2 胜 —— 同一批对局，不可能）。

新版对每一对 (i, j)：
  对每个种子跑两局，i 分别坐座位 0 和座位 1；
  用「谁的座位」明确判断胜负，保证 matrix[i][j] 与 matrix[j][i] 严格互补。
并在最后断言矩阵对称，不通过就直接报错。

用法：
    python roundrobin2.py --agents candidates/*.py --episodes 6
"""
import argparse
import contextlib
import glob
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
    ap.add_argument("--seed-base", type=int, default=600000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    paths = []
    for pat in args.agents:
        g = sorted(glob.glob(pat))
        paths.extend(g if g else [pat])
    paths = [p for p in paths if os.path.exists(p)]
    names = [os.path.basename(p).replace(".py", "") for p in paths]
    agents = {n: load(p) for n, p in zip(names, paths)}
    seeds = [args.seed_base + i for i in range(args.episodes)]

    # matrix[a][b] = [a 胜, 平, b 胜]
    matrix = {a: {b: [0, 0, 0] for b in names if b != a} for a in names}
    money = {n: [] for n in names}
    margins = {n: [] for n in names}

    for a, b in itertools.combinations(names, 2):
        for seed in seeds:
            for a_seat in (0, 1):
                first, second = (a, b) if a_seat == 0 else (b, a)
                env = make("kaggriculture",
                           configuration={"episodeSteps": args.steps, "seed": seed},
                           debug=False)
                env.run([agents[first], agents[second]])
                f = env.steps[-1]
                if f[0].status != "DONE" or f[1].status != "DONE":
                    continue
                m_first = float(f[0].reward or 0)
                m_second = float(f[1].reward or 0)
                # 换算成 a / b 的得分
                ma, mb = (m_first, m_second) if a_seat == 0 else (m_second, m_first)
                money[a].append(ma)
                money[b].append(mb)
                margins[a].append(ma - mb)
                margins[b].append(mb - ma)
                if ma > mb:
                    matrix[a][b][0] += 1
                    matrix[b][a][2] += 1
                elif ma < mb:
                    matrix[b][a][0] += 1
                    matrix[a][b][2] += 1
                else:
                    matrix[a][b][1] += 1
                    matrix[b][a][1] += 1

    # 断言对称性
    bad = []
    for a, b in itertools.combinations(names, 2):
        wa, ta, la = matrix[a][b]
        wb, tb, lb = matrix[b][a]
        if not (wa == lb and la == wb and ta == tb):
            bad.append((a, b, matrix[a][b], matrix[b][a]))

    lines = [f"循环赛（修正版）：{', '.join(names)}",
             f"种子 {seeds[0]}–{seeds[-1]}（{len(seeds)} 个）× 双座位", ""]

    if bad:
        lines.append("!! 对称性校验失败，结果不可信：")
        for a, b, ab, ba in bad:
            lines.append(f"   {a} vs {b}: {ab} / {ba}")
    else:
        lines.append("对称性校验: 通过（每个组合双方局数互补）")

    lines.append("")
    lines.append(f"{'agent':<12} {'战绩':>14} {'胜率':>7} {'平均资金':>11} {'平均分差':>11}")
    lines.append("-" * 62)
    ranking = []
    for n in names:
        w = sum(matrix[n][b][0] for b in names if b != n)
        l = sum(matrix[n][b][2] for b in names if b != n)
        t = sum(matrix[n][b][1] for b in names if b != n)
        tot = w + l + t
        wr = w / tot if tot else 0
        ranking.append((n, wr))
        lines.append(f"{n:<12} {f'{w}W-{l}L-{t}T':>14} {wr:>7.0%} "
                     f"{statistics.mean(money[n]) if money[n] else 0:>11,.0f} "
                     f"{statistics.mean(margins[n]) if margins[n] else 0:>+11,.0f}")

    lines.append("")
    lines.append("两两对打（严格互补）：")
    for a in names:
        parts = []
        for b in names:
            if a == b:
                continue
            w, t, l = matrix[a][b]
            parts.append(f"{b}:{w}W-{l}L")
        lines.append(f"  {a:<12} " + "  ".join(parts))

    ranking.sort(key=lambda r: -r[1])
    lines.append("")
    lines.append("按胜率排序：" + " > ".join(f"{n}({wr:.0%})" for n, wr in ranking))

    text = "\n".join(lines)
    with open("_docx/roundrobin2.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
