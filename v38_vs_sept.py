"""
V38 对 12 个 9 月真实高分 agent（rating 2,809-2,908）严格对打。

目的：判断是否存在比 V38 更强的基座。
判据：若某个 9 月 agent 对 V38 胜率 > 50%（多子集、几十局），则它是更好的候选。

局限：9 月 agent 是从回放还原的**固定动作表**，只对各自地图最优；
换到探测地图会退化。因此本测试对它们不利 ——
若它们在此条件下仍能压制 V38，那是很强的信号；
若被压制，则不能完全排除（可能只是地图不匹配）。
"""
import contextlib
import glob
import io
import os
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


V38 = load("candidates/V38.py")
SEEDS = [1100000 + i for i in range(6)]   # 6 种子 × 双座位 = 12 局/对手

files = sorted(glob.glob("opponents_src/sept/sept_*.py"))
out = [f"V38 vs 9 月高分 agent（{len(files)} 个，{len(SEEDS)} 种子 × 双座位）", ""]
out.append(f"{'对手 episode':>14} {'V38胜':>7} {'对手胜':>7} {'V38胜率':>8} "
           f"{'V38均资金':>11} {'对手均资金':>11}")
out.append("-" * 74)

tot_w = tot_l = 0
per = []
for f in files:
    opp = load(f)
    eid = os.path.basename(f).split("_")[1]
    w = l = 0
    mm, mo = [], []
    for seed in SEEDS:
        for v_seat in (0, 1):
            first, second = (V38, opp) if v_seat == 0 else (opp, V38)
            env = make("kaggriculture",
                       configuration={"episodeSteps": 720, "seed": seed}, debug=False)
            env.run([first, second])
            st = env.steps[-1]
            if st[0].status != "DONE" or st[1].status != "DONE":
                continue
            m0, m1 = float(st[0].reward or 0), float(st[1].reward or 0)
            a, b = (m0, m1) if v_seat == 0 else (m1, m0)
            mm.append(a)
            mo.append(b)
            if a > b:
                w += 1
            elif b > a:
                l += 1
    tot_w += w
    tot_l += l
    n = w + l
    per.append((eid, w, l))
    out.append(f"{eid:>14} {w:>7} {l:>7} {w/n if n else 0:>8.1%} "
               f"{statistics.mean(mm) if mm else 0:>11,.0f} "
               f"{statistics.mean(mo) if mo else 0:>11,.0f}")

n = tot_w + tot_l
out.append("")
out.append(f"合计 V38 {tot_w}W-{tot_l}L   胜率 {tot_w/n:.1%}" if n else "无数据")
wins = sum(1 for _, w, l in per if w > l)
out.append(f"V38 占优的对手数: {wins}/{len(per)}")
out.append("")
out.append("判据：若某对手对 V38 胜率 > 50%，它可能是更好的基座。")
losers = [(e, w, l) for e, w, l in per if l > w]
if losers:
    out.append("对 V38 占优的对手：")
    for e, w, l in losers:
        out.append(f"  ep {e}: 对手 {l}W-{w}L")
else:
    out.append("没有对手对 V38 占优 → V38 仍是最强基座")

text = "\n".join(out)
with open("_docx/v38_vs_sept.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
