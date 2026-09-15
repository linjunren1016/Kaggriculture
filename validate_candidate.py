"""
候选提交件的自对局校验：复现 Kaggle 上传时跑的 Validation Episode。

Kaggle 在上传时会让你和自己打一局；任何异常都会让该次提交标记为 Error。
这个脚本在本地先跑一遍，避免把会报错的提交传上去。
"""
import contextlib
import io
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

SPEC = sys.argv[1] if len(sys.argv) > 1 else "main.py"
SEEDS = [1000, 1001, 4321]

out = [f"自对局校验: {SPEC}", ""]
raw = open(SPEC, encoding="utf-8").read()
fn = get_last_callable(raw, path=SPEC)
out.append(f"加载器选中: {getattr(fn, '__name__', None)}")

ok_all = True
for seed in SEEDS:
    env = make("kaggriculture",
               configuration={"episodeSteps": 720, "seed": seed}, debug=True)
    env.run([fn, fn])
    f = env.steps[-1]
    st = [s.status for s in f]
    rw = [float(s.reward or 0) for s in f]
    ok = all(x == "DONE" for x in st)
    ok_all = ok_all and ok
    out.append(f"  seed {seed}: 状态 {st}  资金 {rw[0]:,.0f} / {rw[1]:,.0f}  "
               f"{'OK' if ok else 'FAILED'}")

out.append("")
out.append("RESULT: " + ("PASS - 可安全上传" if ok_all else "FAIL - 不要上传"))

text = "\n".join(out)
with open("_docx/validate_cand.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
