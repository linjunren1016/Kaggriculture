"""
提取 notebook 里所有内嵌的 agent 源码，支持多种变量名与编码。

已知的 artifact 与作者公布的 SHA-256：
  C92  7b13e69371509fe53f1dbb7b769d73f6c82ff41db37df7a9a3a1879e82ed82f2
  C94  7b0e5a7b9d18dc583f5789e50a54dca43561f6d08c1c616b4219bf50bcb8311f
  C95  489f5d197527f107027626cce79d850fd2ca90edd43d94384b849b6511e27bdb
"""
import ast
import base64
import hashlib
import json
import re
import zlib

NB = "opponents_src/kaggriculture-findings-from-zero-to-top-meta.ipynb"

KNOWN = {
    "7b13e69371509fe53f1dbb7b769d73f6c82ff41db37df7a9a3a1879e82ed82f2": "C92",
    "7b0e5a7b9d18dc583f5789e50a54dca43561f6d08c1c616b4219bf50bcb8311f": "C94",
    "489f5d197527f107027626cce79d850fd2ca90edd43d94384b849b6511e27bdb": "C95",
}

with open(NB, encoding="utf-8") as fh:
    nb = json.load(fh)

out = []
found = {}
# 找任何形如 XXX_B64_PARTS / XXX_PARTS / XXX_BLOB 的列表变量
PAT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\[", re.M)

for ci, cell in enumerate(nb["cells"]):
    if cell.get("cell_type") != "code":
        continue
    src = "".join(cell.get("source", []))
    if "sha256" not in src and "zlib" not in src:
        continue

    # 收集所有「长字符串列表」变量
    cands = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            for tg in node.targets:
                if isinstance(tg, ast.Name):
                    try:
                        vals = [ast.literal_eval(e) for e in node.value.elts]
                    except Exception:
                        continue
                    if vals and all(isinstance(v, str) for v in vals) \
                            and sum(len(v) for v in vals) > 5000:
                        cands.append((tg.id, vals))

    for name, vals in cands:
        blob = "".join(vals)
        for dec_name, dec in (("b64", base64.b64decode),
                              ("b85", base64.b85decode),
                              ("a85", base64.a85decode)):
            try:
                raw = dec(blob)
            except Exception:
                continue
            for z_name, zf in (("zlib", lambda b: zlib.decompress(b)),
                               ("raw", lambda b: zlib.decompress(b, -15)),
                               ("plain", lambda b: b)):
                try:
                    data = zf(raw)
                except Exception:
                    continue
                if b"def agent" not in data and b"_submission_agent" not in data:
                    continue
                h = hashlib.sha256(data).hexdigest()
                label = KNOWN.get(h, f"{name}_cell{ci}")
                key = label
                n = 1
                while key in found:
                    n += 1
                    key = f"{label}_{n}"
                found[key] = (data, h, ci)
                out.append(f"cell {ci} 变量 {name}: {len(vals)} 段 → {len(data):,} 字节  "
                           f"{dec_name}/{z_name}  sha256={h[:16]}…")
                break

out.append("")
out.append(f"共提取 {len(found)} 个候选")
for key, (data, h, ci) in sorted(found.items()):
    tag = "  ✔ 与作者公布哈希一致" if h in KNOWN else ""
    fn = f"opponents_src/extracted_{key}.py"
    with open(fn, "wb") as fh2:
        fh2.write(data)
    out.append(f"  {key:<28} {len(data):>8,} 字节  cell{ci}{tag}")
    out.append(f"     → {fn}")

with open("_docx/extract_all.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out))
