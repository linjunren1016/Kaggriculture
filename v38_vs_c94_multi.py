"""
在 V38 与 C94 之间做多子集交叉判定。

背景：两者此前各赢一批种子（V38 在种子 400000+ 赢 72.5%，C94 在 600000+ 赢 67%），
说明不是稳定优势。而行为签名统计显示 C94 明显更接近真实顶尖层
（签名偏差 0.056 vs 0.138；SELL 180 vs 502 对比顶尖层 189）。

本脚本在 6 个互不重叠的种子集上各跑一轮，看谁的总胜率更稳。
"""
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


V38 = load("candidates/V38.py")
C94 = load("candidates/C94.py")

BLOCKS = [(1000000, 1000009), (1010000, 1010009), (1020000, 1020009),
          (1030000, 1030009), (1040000, 1040009), (1050000, 1050009)]

out = ["V38 vs C94 —— 6 个互不重叠种子集交叉判定", ""]
out.append(f"{'种子集':<22} {'V38胜':>7} {'C94胜':>7} {'V38胜率':>9}")
out.append("-" * 50)
tot_v = tot_c = 0
per_block = []
for lo, hi in BLOCKS:
    v = c = 0
    for seed in range(lo, hi + 1):
        for v_seat in (0, 1):
            first, second = (V38, C94) if v_seat == 0 else (C94, V38)
            env = make("kaggriculture",
                       configuration={"episodeSteps": 720, "seed": seed}, debug=False)
            env.run([first, second])
            f = env.steps[-1]
            if f[0].status != "DONE" or f[1].status != "DONE":
                continue
            m0, m1 = float(f[0].reward or 0), float(f[1].reward or 0)
            mv, mc = (m0, m1) if v_seat == 0 else (m1, m0)
            if mv > mc:
                v += 1
            elif mc > mv:
                c += 1
    tot_v += v
    tot_c += c
    n = v + c
    per_block.append((f"{lo}-{hi}", v, c, v / n if n else 0))
    out.append(f"{f'{lo}-{hi}':<22} {v:>7} {c:>7} {v/n if n else 0:>9.1%}")

n = tot_v + tot_c
out.append("")
out.append(f"总计 V38 {tot_v}W  C94 {tot_c}W   总 {n} 局")
out.append(f"V38 总胜率 {tot_v/n:.1%}")
wins = sum(1 for _, v, c, _ in per_block if v > c)
out.append(f"V38 占优的种子集: {wins}/{len(BLOCKS)}")
if wins >= 5:
    out.append("=> V38 更稳")
elif wins <= 1:
    out.append("=> C94 更稳")
else:
    out.append("=> 两者无稳定差异（种子依赖）")

text = "\n".join(out)
with open("_docx/v38_vs_c94_multi.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
