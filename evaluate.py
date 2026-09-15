"""
固定评测台（eval harness）。

为什么需要它
------------
调参过程中很容易反复使用同一批种子做决策，把它们"用脏"。之前 HIRE_CAP 的
8-vs-6 和 8-vs-10 都跑在种子 6000–6011 上，严格说这批种子已经不再是纯净留出集。

本脚本用两套互不重叠的种子：
  --tune   ：开发时可随便用（会被反复使用，结果仅供快速筛选）
  --accept ：**只用于验收**，禁止在调参过程中查看，避免选择性偏差

只有 --accept 上的结果才算数。

用法：
    python evaluate.py --mode tune                 # 快速迭代
    python evaluate.py --mode accept               # 采纳改动前跑一次
    python evaluate.py --mode accept --archive submission.tar.gz
"""
import argparse
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

# 开发用种子：允许反复使用
TUNE_SEEDS = list(range(8000, 8010))
# 验收种子：只在验收时使用，不得用于筛选改动
ACCEPT_SEEDS = list(range(9000, 9020))

OPPONENTS = ["pass", "starter"]


def play(agent, opponent, seed, steps):
    env = make("kaggriculture",
               configuration={"episodeSteps": steps, "seed": seed}, debug=True)
    env.run([agent, opponent])
    f = env.steps[-1]
    return float(f[0].reward or 0.0), float(f[1].reward or 0.0), f[0].status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["tune", "accept"], default="tune")
    ap.add_argument("--agent", default="main.py")
    ap.add_argument("--archive", default=None,
                    help="check the packaged archive instead of main.py")
    ap.add_argument("--opponents", nargs="*", default=OPPONENTS)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    agent = args.agent
    if args.archive:
        import os
        import tarfile
        import tempfile
        workdir = tempfile.mkdtemp(prefix="kaggeval_")
        with tarfile.open(args.archive) as tf:
            tf.extractall(workdir)
        agent = os.path.join(workdir, "main.py")

    seeds = ACCEPT_SEEDS if args.mode == "accept" else TUNE_SEEDS
    lines = [f"评测 [{args.mode}]  agent={args.archive or args.agent}",
             f"种子 {seeds[0]}–{seeds[-1]}（{len(seeds)} 个），双方各坐一次 → "
             f"{len(seeds) * 2} 局/对手", ""]

    overall = []
    for opp in args.opponents:
        rows = []
        for seed in seeds:
            # 座位0
            m, o, st = play(agent, opp, seed, args.steps)
            if st == "DONE":
                rows.append((m, o))
            # 座位1
            m, o, st = play(opp, agent, seed, args.steps)
            if st == "DONE":
                rows.append((o, m))

        wins = sum(1 for m, o in rows if m > o)
        losses = sum(1 for m, o in rows if m < o)
        ties = len(rows) - wins - losses
        money = statistics.mean(m for m, _ in rows)
        margin = statistics.mean(m - o for m, o in rows)
        lines.append(f"vs {opp:<9} {wins}W-{losses}L-{ties}T  "
                     f"win={wins/len(rows):.3f}  "
                     f"money=${money:>10,.0f}  margin=${margin:>+10,.0f}")
        overall.extend(rows)

    allwin = sum(1 for m, o in overall if m > o)
    lines.append("")
    lines.append(f"合计 {allwin}W-{len(overall)-allwin}L   "
                 f"平均资金 ${statistics.mean(m for m, _ in overall):,.0f}   "
                 f"平均分差 ${statistics.mean(m - o for m, o in overall):+,.0f}")
    if args.mode == "accept":
        lines.append("")
        lines.append("（验收结果；开发调参请勿参考本模式，以免污染留出集）")

    text = "\n".join(lines)
    with open(f"_docx/eval_{args.mode}.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
