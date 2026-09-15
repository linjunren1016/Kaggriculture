"""
留出集验证：用「没参与调参」的种子，对比留出的候选配置。

调参时在同一批种子上比过多个取值，会有过拟合风险（挑到运气好的那个）。
这里用一组全新种子复验，只有在新种子上依然占优的改动才值得保留。
"""
import argparse
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")


def run_config(param, value, seeds, steps, opponent="pass"):
    for m in list(sys.modules):
        if m == "main":
            del sys.modules[m]
    import main
    if value is not None:
        setattr(main, param, value)
    outs = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": steps, "seed": seed}, debug=False)
        env.run([main.agent, opponent])
        outs.append(float(env.steps[-1][0].reward or 0.0))
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--param", default="HIRE_CAP")
    ap.add_argument("--a", type=int, default=6)
    ap.add_argument("--b", type=int, default=8)
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--seed-base", type=int, default=5000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    seeds = [args.seed_base + i for i in range(args.episodes)]
    lines = [f"留出集验证 {args.param}: {args.a} vs {args.b}",
             f"全新种子 {seeds}（未参与调参）", ""]

    ra = run_config(args.param, args.a, seeds, args.steps)
    rb = run_config(args.param, args.b, seeds, args.steps)

    lines.append(f"{args.param}={args.a}: 平均 {statistics.mean(ra):,.0f}  "
                 f"最低 {min(ra):,.0f}  最高 {max(ra):,.0f}")
    lines.append(f"{args.param}={args.b}: 平均 {statistics.mean(rb):,.0f}  "
                 f"最低 {min(rb):,.0f}  最高 {max(rb):,.0f}")
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    lines.append("")
    lines.append(f"差异: {mb - ma:+,.0f}  ({(mb/ma - 1)*100:+.1f}%)")

    wins_b = sum(1 for x, y in zip(ra, rb) if y > x)
    lines.append(f"{args.b} 胜出的种子数: {wins_b}/{len(seeds)}")
    lines.append("")
    if wins_b == len(seeds):
        lines.append("=> 新种子上全部占优，可信")
    elif wins_b >= len(seeds) * 0.7:
        lines.append("=> 新种子上多数占优，较可信")
    else:
        lines.append("=> 新种子上并不稳定占优，疑似过拟合，不建议采纳")

    with open("_docx/holdout.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("done")


if __name__ == "__main__":
    sys.exit(main())
