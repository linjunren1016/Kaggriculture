"""从 adaptive-farming notebook 提取 TOP_AGENT_FILES 里的明文源码。"""
import ast
import hashlib
import json
import os

TARGET = "opponents_src/adaptive-farming-strategy-for-kaggriculture.ipynb"
OUTDIR = "opponents_src/v38_src"

with open(TARGET, encoding="utf-8") as fh:
    nb = json.load(fh)

os.makedirs(OUTDIR, exist_ok=True)
out = []
found = {}
for ci, cell in enumerate(nb["cells"]):
    if cell.get("cell_type") != "code":
        continue
    src = "".join(cell.get("source", []))
    if "TOP_AGENT_FILES" not in src and "AGENT_FILES" not in src:
        continue
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not any(n in ("TOP_AGENT_FILES", "AGENT_FILES") for n in names):
            continue
        try:
            val = ast.literal_eval(node.value)
        except Exception:
            # 可能是 dict(...) 调用或拼接
            try:
                # 尝试用受限 eval
                val = eval(compile(ast.Expression(node.value), "<x>", "eval"), {})
            except Exception as exc:
                out.append(f"cell {ci} {names}: 无法求值 {type(exc).__name__}")
                continue
        if not isinstance(val, dict):
            out.append(f"cell {ci} {names}: 不是 dict ({type(val).__name__})")
            continue
        out.append(f"cell {ci} 变量 {names}: dict，{len(val)} 个键")
        for k, v in val.items():
            if not isinstance(v, str):
                out.append(f"   {k}: 非字符串 ({type(v).__name__})")
                continue
            out.append(f"   {k}: {len(v):,} 字符")
            fn = os.path.join(OUTDIR, os.path.basename(str(k)))
            with open(fn, "w", encoding="utf-8") as f2:
                f2.write(v)
            h = hashlib.sha256(v.encode()).hexdigest()
            out.append(f"      → {fn}   sha256={h[:16]}…")
            found[str(k)] = (len(v), h, fn)

if not found:
    out.append("")
    out.append("未找到明文源码；尝试列出该 notebook 的 code cell 里所有大写变量名：")
    for ci, cell in enumerate(nb["cells"]):
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        import re
        for m in re.finditer(r"^([A-Z][A-Z0-9_]{3,})\s*=", src, re.M):
            out.append(f"   cell {ci}: {m.group(1)}")

with open("_docx/v38_files.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out))
