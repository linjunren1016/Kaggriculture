"""
V38 vs 9 月 meta 配方 agent —— 同一张地图上的公平对打。

为什么重要：
  我提取的 9 月 agent 中有 14 个**精确符合当前 meta 配方**
  （草莓33/小麦163/甜瓜12/胡萝卜31/总239/雇工12，匹配度 0.001），
  评分 2,790-2,905。它们代表当前顶尖打法。

此前测过 V38 对它们 91.7% 胜率，但那次是**在对手各自的原地图**上，
而固定动作表在原地图最强 —— 那个测试**对它们有利**，V38 仍赢，
说明 V38 不弱。

这次反向验证：若在某张统一地图上（双方都不在"主场"），
meta 配方 agent 仍能赢 V38，则说明配方本身更强。
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
SEEDS = [1600000 + i for i in range(5)]

# 只挑匹配度高的：以 episode id 列出（来自 modal_match.txt）
MODAL = ["108014559", "108050837", "108062853", "108088866",
         "108089814", "108026392", "108056090", "107983407"]

files = []
for eid in MODAL:
    g = glob.glob(f"opponents_src/sept/sept_{eid}_s*.py")
    files.extend(g)

out = [f"V38 vs 9 月 meta 配方 agent（统一地图，{len(SEEDS)} 种子 × 双座位）", ""]
out.append(f"{'对手':>22} {'V38胜':>7} {'对手胜':>7} {'V38胜率':>8} "
           f"{'V38均资金':>11} {'对手均资金':>11}")
out.append("-" * 72)

tw = tl = 0
for f in files:
    opp = load(f)
    name = os.path.basename(f).replace(".py", "")
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
    tw += w
    tl += l
    n = w + l
    out.append(f"{name:>22} {w:>7} {l:>7} {w/n if n else 0:>8.1%} "
               f"{statistics.mean(mm) if mm else 0:>11,.0f} "
               f"{statistics.mean(mo) if mo else 0:>11,.0f}")

n = tw + tl
out.append("")
if n:
    out.append(f"合计 V38 {tw}W-{tl}L   胜率 {tw/n:.1%}")
    out.append("")
    if tw / n > 0.6:
        out.append("=> V38 更强。meta 配方 agent 在统一地图上打不过 V38。")
    elif tl / n > 0.6:
        out.append("=> meta 配方 agent 更强 —— 应考虑采用其配方。")
    else:
        out.append("=> 两者接近。")

text = "\n".join(out)
with open("_docx/vs_modal.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
