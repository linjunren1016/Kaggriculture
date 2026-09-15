"""
最终提交前检查：完全按 Kaggle 的流程验证 submission.tar.gz。

检查项：
  1. 包结构：main.py 必须位于压缩包根目录
  2. 从包内解压后，用 Kaggle 的 get_last_callable 加载
  3. 加载出的对象可调用，且在真实环境里跑完整 720 回合
  4. 编码无 BOM / 无替换字符；语法可解析
  5. 报告 sha256，便于与提交记录比对
"""
import contextlib
import hashlib
import io
import os
import sys
import tarfile
import tempfile

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

ARCHIVE = "submission.tar.gz"
out = [f"提交前最终检查: {ARCHIVE}", ""]
ok = True


def chk(label, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    out.append(f"  [{'OK ' if cond else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))


# 1) 包结构
tf = tarfile.open(ARCHIVE)
names = tf.getnames()
chk("压缩包含 main.py 且位于根目录", names == ["main.py"], f"成员={names}")

# 2) 解压并加载
workdir = tempfile.mkdtemp(prefix="kaggcheck_")
tf.extractall(workdir)
path = os.path.join(workdir, "main.py")
chk("解压成功", os.path.exists(path))

raw = open(path, "rb").read()
sha = hashlib.sha256(raw).hexdigest()
chk("无字节序标记 BOM", not raw.startswith(b"\xef\xbb\xbf"))
chk("无替换字符 U+FFFD", "\ufffd" not in raw.decode("utf-8", "replace"))

src = raw.decode("utf-8")
try:
    import ast
    ast.parse(src)
    chk("语法可解析", True)
except SyntaxError as exc:
    chk("语法可解析", False, str(exc))

# 3) 用 Kaggle 的规则加载
try:
    fn = get_last_callable(src, path=path)
    name = getattr(fn, "__name__", None)
    chk("加载器返回可调用对象", callable(fn), f"选中={name}")
    chk("选中对象名符合预期", name in ("agent", "_kaggle_submission_entrypoint",
                                       "c94_submission_agent"),
        f"name={name}")
except Exception as exc:
    chk("加载器返回可调用对象", False, f"{type(exc).__name__}: {exc}")

# 4) 真实跑一局
try:
    with contextlib.redirect_stderr(io.StringIO()):
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": 1300000}, debug=False)
        env.run([fn, fn])
    st = env.steps[-1]
    statuses = [s.status for s in st]
    rewards = [float(s.reward or 0) for s in st]
    chk("720 回合自对局跑通", all(x == "DONE" for x in statuses),
        f"状态={statuses}")
    out.append(f"       资金 {rewards[0]:,.0f} / {rewards[1]:,.0f}")
except Exception as exc:
    chk("720 回合自对局跑通", False, f"{type(exc).__name__}: {exc}")

out.append("")
out.append(f"  sha256 = {sha}")
out.append(f"  大小   = {len(raw):,} 字节")
out.append("")
out.append("结论: " + ("全部通过，可以提交" if ok else "**存在问题，不要提交**"))

text = "\n".join(out)
with open("_docx/final_check.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
