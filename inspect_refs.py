"""检查参考 agent 的调度器结构，并对比 meta_line 与 authored 的 POLICY 差异。"""
import ast
import os
import re

BASE = "opponents_src"
FILES = ["melon_mateo.py", "rancher_rita.py", "broker_bea.py",
         "ledger_lena.py", "slotter_silas.py", "closer_cleo.py"]

out = []
for fn in FILES:
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        out.append(f"{fn}: 缺失")
        continue
    src = open(p, encoding="utf-8").read()
    tree = ast.parse(src)
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    # 提取 POLICY
    m = re.search(r"^POLICY\s*=\s*\{(.*?)^\}", src, re.S | re.M)
    policy = m.group(1).strip() if m else "(未找到)"
    out.append("=" * 78)
    out.append(f"{fn}   {len(src)/1024:.1f} KB   函数: {funcs}")
    out.append("  POLICY:")
    for line in policy.splitlines():
        out.append("    " + line.strip())
    out.append("")

# 对比 scheduler 是否字节一致（去掉 POLICY 段）
out.append("=" * 78)
out.append("调度器一致性检验（去掉 POLICY 段后比较其余代码的哈希）")
import hashlib
sigs = {}
for fn in FILES:
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        continue
    src = open(p, encoding="utf-8").read()
    stripped = re.sub(r"^POLICY\s*=\s*\{.*?^\}", "POLICY = {}", src, flags=re.S | re.M)
    # 去掉文件头 docstring（各 tier 不同）
    stripped = re.sub(r'^""".*?"""', "", stripped, flags=re.S)
    h = hashlib.sha256(stripped.encode()).hexdigest()[:16]
    sigs[fn] = h
    out.append(f"  {fn:<22} {h}")
uniq = set(sigs.values())
out.append(f"  唯一哈希数: {len(uniq)} / {len(sigs)}"
           + ("  ← 调度器完全一致" if len(uniq) == 1 else "  ← 存在差异"))

with open("_docx/ref_agents.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out))
