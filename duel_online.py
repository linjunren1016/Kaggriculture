"""
用线上对手（从回放提取的固定动作序列）在本地对练。

用途：把"线上到底行不行"变成一个可本地测量的胜负问题。
ZZDW_ 是打赢过我们的真实对手，且在不同对局中稳定打出 16k–30k。

注意固定动作表的固有限制：动作序列只对它当初那张地图最优，
换种子后布局不同，它的表现会下降。所以要看多个种子上的综合结果，
不要只看它原始那张。

用法：
    python duel_online.py --episodes 8
"""
import argparse
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def play(a, b, seed, steps):
    env = make("kaggriculture",
               configuration={"episodeSteps": steps, "seed": seed}, debug=True)
    env.run([a, b])
    f = env.steps[-1]
    return float(f[0].reward or 0), float(f[1].reward or 0), f[0].status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="main.py")
    ap.add_argument("--b", default="opponents/zzdw.py")
    ap.add_argument("--episodes", type=int, default=8)
    ap.add_argument("--seed-base", type=int, default=20000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    lines = [f"本地对练：{args.a}  vs  {args.b}",
             f"种子 {args.seed_base}–{args.seed_base+args.episodes-1}，双方各坐一次", ""]
    rows = []
    for i in range(args.episodes):
        seed = args.seed_base + i
        m, o, st = play(args.a, args.b, seed, args.steps)
        if st == "DONE":
            rows.append((m, o, seed, "a先"))
        m, o, st = play(args.b, args.a, seed, args.steps)
        if st == "DONE":
            rows.append((o, m, seed, "a后"))

    if not rows:
        lines.append("无有效对局")
    else:
        wins = sum(1 for m, o, _, _ in rows if m > o)
        lines.append(f"{'我方':>10} {'对手':>10} {'结果':>4}  种子")
        for m, o, seed, seat in sorted(rows, key=lambda r: -r[0]):
            lines.append(f"{m:>10,.0f} {o:>10,.0f} {'胜' if m > o else '负':>4}  {seed} ({seat})")
        lines.append("")
        lines.append(f"战绩 {wins}胜 {len(rows)-wins}负   胜率 {wins/len(rows):.1%}")
        lines.append(f"平均我方 ${statistics.mean(m for m,_,_,_ in rows):,.0f}   "
                     f"对手 ${statistics.mean(o for _,o,_,_ in rows):,.0f}")
        lines.append(f"平均分差 ${statistics.mean(m-o for m,o,_,_ in rows):+,.0f}")

    text = "\n".join(lines)
    with open("_docx/duel_online.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
