"""验证 ZZDW_ 的本地复现是否忠实：用它原本的种子跑，对比原始得分。"""
import contextlib
import io
import sys

sys.path.insert(0, ".")
with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

CASES = [
    # (seed, 原始得分, 说明)
    (514258450, 28256.0, "episode-109170440 对 quwon_000"),
    (1448588929, 16380.0, "episode-109163396 对 Divyansh82Raj"),
    (375165781, 27940.0, "episode-109162351 对 Yash Apps"),
]

out = ["ZZDW_ 本地复现验证（对手 pass，用原局 seed）", ""]
for seed, original, note in CASES:
    env = make("kaggriculture",
               configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(["opponents/zzdw.py", "pass"])
    f = env.steps[-1]
    got = float(f[0].reward or 0)
    out.append(f"seed {seed}  ({note})")
    out.append(f"   原始得分 {original:>10,.0f}   本地复现 {got:>10,.0f}   "
               f"差异 {got - original:>+10,.0f}   状态 {f[0].status}")
    out.append("")

with open("_docx/zzdw_verify.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
