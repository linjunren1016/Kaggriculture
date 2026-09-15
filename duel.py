"""
两个 Agent 之间的成对对抗（双座位）。

用法：
    python duel.py --a main.py --b sparring_melon.py --episodes 5
"""
import argparse
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def one(a, b, seed, steps):
    env = make("kaggriculture",
               configuration={"episodeSteps": steps, "seed": seed}, debug=True)
    env.run([a, b])
    f = env.steps[-1]
    return float(f[0].reward or 0), float(f[1].reward or 0), f[0].status, f[1].status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="main.py")
    ap.add_argument("--b", default="sparring_melon.py",
                    help="set to 'pass' to measure A's absolute money instead")
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    lines = []
    a_first, b_first = [], []   # a 作为座位0 / a 作为座位1
    for i in range(args.episodes):
        seed = 3000 + i
        am, bm, s0, s1 = one(args.a, args.b, seed, args.steps)
        if s0 == "DONE" and s1 == "DONE":
            a_first.append((am, bm))
        bm2, am2, s0, s1 = one(args.b, args.a, seed, args.steps)
        if s0 == "DONE" and s1 == "DONE":
            b_first.append((am2, bm2))

        aw = sum(1 for m, o in a_first if m > o) + sum(1 for m, o in b_first if m > o)
        al = sum(1 for m, o in a_first if m < o) + sum(1 for m, o in b_first if m < o)
        lines.append(f"seed {seed}: 累计 {args.a} {aw}胜 {al}负")

    def rep(label, res):
        if not res:
            lines.append(f"  {label}: 无有效对局")
            return
        w = sum(1 for m, o in res if m > o)
        l = sum(1 for m, o in res if m < o)
        t = len(res) - w - l
        mm = statistics.mean(m - o for m, o in res)
        lines.append(f"  {label:<22} {w}W-{l}L-{t}T  win_rate={w/len(res):.3f}  "
                     f"mean_margin={mm:+9.0f}  avg_money={statistics.mean(m for m,_ in res):9.0f}")

    total = a_first + b_first
    lines.append("")
    lines.append(f"=== {args.a}  vs  {args.b} ===")
    rep(f"{args.a} 座位0", a_first)
    rep(f"{args.a} 座位1", b_first)
    rep(f"{args.a} 合计", total)
    if total:
        aw = sum(1 for m, o in total if m > o)
        lines.append("")
        lines.append(f"结论：{args.a} 对 {args.b} 胜率 {aw/len(total):.1%} "
                     f"（{len(total)} 局，{args.episodes} 个种子 × 2 座位）")
        if aw / len(total) > 0.6:
            lines.append(f"=> {args.a} 明显更强")
        elif aw / len(total) < 0.4:
            lines.append(f"=> {args.b} 明显更强")
        else:
            lines.append("=> 两者接近，区分度有限")

    with open("_docx/duel.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("done")


if __name__ == "__main__":
    sys.exit(main())
