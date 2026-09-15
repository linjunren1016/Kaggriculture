"""
最简对打校验：逐局打印胜负，确保记账无误。

用途：在有多个评测脚本给出矛盾结论时，用最小实现确定真相。
不聚合、不取平均，直接列出每一局的双方资金与胜负。
"""
import argparse
import contextlib
import io
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


ap = argparse.ArgumentParser()
ap.add_argument("--a", required=True)
ap.add_argument("--b", required=True)
ap.add_argument("--seeds", required=True, help="如 400000-400019 或逗号分隔")
ap.add_argument("--steps", type=int, default=720)
args = ap.parse_args()

if "-" in args.seeds:
    lo, hi = args.seeds.split("-")
    seeds = list(range(int(lo), int(hi) + 1))
else:
    seeds = [int(x) for x in args.seeds.split(",")]

A, B = load(args.a), load(args.b)
out = [f"A = {args.a}", f"B = {args.b}", f"种子 {seeds[0]}–{seeds[-1]}（{len(seeds)} 个）× 双座位", ""]

aw = bw = tie = 0
rows = []
for seed in seeds:
    for a_seat in (0, 1):
        first, second = (A, B) if a_seat == 0 else (B, A)
        env = make("kaggriculture",
                   configuration={"episodeSteps": args.steps, "seed": seed}, debug=False)
        env.run([first, second])
        f = env.steps[-1]
        s0 = f[0].status
        s1 = f[1].status
        r0 = float(f[0].reward or 0)
        r1 = float(f[1].reward or 0)
        if s0 != "DONE" or s1 != "DONE":
            rows.append(f"seed {seed} A座位{a_seat}: 状态异常 {s0}/{s1} —— 跳过")
            continue
        ma, mb = (r0, r1) if a_seat == 0 else (r1, r0)
        if ma > mb:
            res = "A胜"
            aw += 1
        elif ma < mb:
            res = "B胜"
            bw += 1
        else:
            res = "平"
            tie += 1
        rows.append(f"seed {seed} A座位{a_seat}: A={ma:>9,.0f}  B={mb:>9,.0f}  {res}")

out.extend(rows)
out.append("")
out.append(f"A 胜 {aw}    B 胜 {bw}    平 {tie}    总 {aw+bw+tie}")
if aw + bw + tie:
    out.append(f"A 胜率 {aw/(aw+bw+tie):.1%}")
out.append("")
out.append("判定: " + ("A 更强" if aw > bw else ("B 更强" if bw > aw else "打平")))

text = "\n".join(out)
with open("_docx/h2h.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text[-1500:])
