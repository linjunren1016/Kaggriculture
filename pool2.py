"""
彻底提取：扫描已下载的全部 notebook，用多种方式找出内嵌 agent 源码。

覆盖的封装形式：
  1. 压缩列表：base64 / base85 / ascii85 + zlib / raw-deflate / gzip
  2. 明文 dict：TOP_AGENT_FILES['main.py'] 之类
  3. 明文长字符串赋值：SRC = '''...''' 或 json 字符串
  4. writefile / write_text 直接写出
"""
import ast
import base64
import glob
import hashlib
import json
import os
import re
import zlib

OUTDIR = "opponents_src/pool2"
os.makedirs(OUTDIR, exist_ok=True)

out = []
saved = {}

DECODERS = [("b64", base64.b64decode), ("b85", base64.b85decode),
            ("a85", base64.a85decode)]
INFLATERS = [("zlib", lambda b: zlib.decompress(b)),
             ("raw", lambda b: zlib.decompress(b, -15)),
             ("gzip", lambda b: zlib.decompress(b, 16 + zlib.MAX_WBITS)),
             ("plain", lambda b: b)]


def try_decode(blob):
    """尝试所有解码组合，返回含 def 的源码 bytes。"""
    for dn, dec in DECODERS:
        try:
            raw = dec(blob)
        except Exception:
            continue
        for zn, zf in INFLATERS:
            try:
                data = zf(raw)
            except Exception:
                continue
            if b"def " in data and len(data) > 1500:
                return data, f"{dn}/{zn}"
    return None, None


for path in sorted(glob.glob("opponents_src/*.ipynb")):
    nbname = re.sub(r"[^A-Za-z0-9_]", "_",
                    os.path.basename(path).replace(".ipynb", ""))[:24]
    with open(path, encoding="utf-8") as fh:
        nb = json.load(fh)

    hits = []
    for ci, cell in enumerate(nb["cells"]):
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        if len(src) < 500:
            continue

        # --- 1/2/3: AST 找长字符串列表 / 明文 dict / 长字符串 ---
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None

        if tree:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                tag = names[0] if names else "?"

                # 列表（压缩）
                if isinstance(node.value, ast.List):
                    try:
                        vals = [ast.literal_eval(e) for e in node.value.elts]
                    except Exception:
                        continue
                    if vals and all(isinstance(v, str) for v in vals) \
                            and sum(len(v) for v in vals) > 1500:
                        data, how = try_decode("".join(vals))
                        if data:
                            hits.append((tag, data, how, ci))

                # dict（明文）
                elif isinstance(node.value, ast.Dict):
                    try:
                        val = ast.literal_eval(node.value)
                    except Exception:
                        continue
                    if isinstance(val, dict):
                        for k, v in val.items():
                            if isinstance(v, str) and len(v) > 1500 \
                                    and "def " in v:
                                hits.append((f"{tag}[{k}]", v.encode("utf-8"),
                                             "plain-dict", ci))

                # 长字符串（明文，可能是混淆前）
                elif isinstance(node.value, ast.Constant) \
                        and isinstance(node.value.value, str) \
                        and len(node.value.value) > 3000 \
                        and "def " in node.value.value:
                    hits.append((tag, node.value.value.encode("utf-8"),
                                 "plain-str", ci))

        # --- 4: writefile 里的明文 ---
        for m in re.finditer(r"%%writefile\s+(\S+)", src):
            pass  # 留作后续扩展

    for tag, data, how, ci in hits:
        h = hashlib.sha256(data).hexdigest()
        fn = f"{OUTDIR}/{nbname}_c{ci}_{h[:8]}.py"
        if not os.path.exists(fn):
            with open(fn, "wb") as f2:
                f2.write(data)
        out.append(f"{os.path.basename(path)}")
        out.append(f"   cell{ci}  {tag}  方式={how}  {len(data):,}B  "
                   f"sha256={h[:12]}  → {fn}")
        saved[h[:12]] = (len(data), os.path.basename(path))

out.append("")
out.append(f"共 {len(saved)} 个唯一 agent")
for h, (n, src) in sorted(saved.items(), key=lambda kv: -kv[1][0]):
    out.append(f"  {h}  {n:>9,} B   来自 {src}")

text = "\n".join(out)
with open("_docx/pool2.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
