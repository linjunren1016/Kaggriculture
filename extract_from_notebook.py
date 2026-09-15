"""
从公开 notebook 提取内嵌 agent 源码（C92 / C94 / C95）。

数据形式：`_AGENT_B64_PARTS = [ "...", "...", ... ]`
  → base64 解码 → 拼接 → zlib 解压 → 源码

用作者公布的 SHA-256 校验，确保与发布版本完全一致。
"""
import ast
import base64
import hashlib
import json
import zlib

NB = "opponents_src/kaggriculture-findings-from-zero-to-top-meta.ipynb"

KNOWN = {
    "7b13e69371509fe53f1dbb7b769d73f6c82ff41db37df7a9a3a1879e82ed82f2": "C92",
    "7b0e5a7b9d18dc583f5789e50a54dca43561f6d08c1c616b4219bf50bcb8311f": "C94",
}

with open(NB, encoding="utf-8") as fh:
    nb = json.load(fh)

out = []
found = {}
for ci, cell in enumerate(nb["cells"]):
    if cell.get("cell_type") != "code":
        continue
    src = "".join(cell.get("source", []))
    if "_AGENT_B64_PARTS" not in src:
        continue

    # 用 ast 解析出那个列表字面量
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        out.append(f"cell {ci}: 语法解析失败 {exc}")
        continue

    parts = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg, ast.Name) and tg.id == "_AGENT_B64_PARTS":
                    parts = [ast.literal_eval(e) for e in node.value.elts]
    if parts is None:
        out.append(f"cell {ci}: 未找到 _AGENT_B64_PARTS")
        continue

    blob = "".join(parts)
    try:
        data = zlib.decompress(base64.b64decode(blob))
    except Exception as exc:
        out.append(f"cell {ci}: 解码失败 {type(exc).__name__}: {exc}")
        continue

    h = hashlib.sha256(data).hexdigest()
    label = KNOWN.get(h)
    if label is None:
        # 从源码里找绑定名推断
        if b"c94" in data.lower():
            label = f"C94ish_cell{ci}"
        elif b"c95" in data.lower():
            label = f"C95ish_cell{ci}"
        else:
            label = f"unknown_cell{ci}"
    tag = "  ← 与作者公布哈希一致 ✔" if h in KNOWN else "  ← 哈希未在已知列表"
    out.append(f"cell {ci}: {len(parts)} 段 → {len(data):,} 字节  "
               f"sha256={h[:20]}...  → {label}{tag}")

    fn = f"opponents_src/extracted_{label}.py"
    with open(fn, "wb") as fh2:
        fh2.write(data)
    out.append(f"    已写出 {fn}")
    found[label] = (data, h, fn)

out.append("")
out.append(f"共提取 {len(found)} 个 agent")
for label, (data, h, fn) in found.items():
    first = data.splitlines()[0].decode("utf-8", "replace")[:70] if data else ""
    out.append(f"  {label:<18} {len(data):>8,} 字节  首行: {first}")

with open("_docx/extract_nb.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out))
