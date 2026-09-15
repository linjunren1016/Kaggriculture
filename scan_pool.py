"""扫描所有 notebook，找出任何形式的可提取 agent（压缩或明文），并保存。"""
import ast
import base64
import glob
import hashlib
import json
import os
import re
import zlib

OUTDIR = "opponents_src/pool"
os.makedirs(OUTDIR, exist_ok=True)

out = []
saved = {}

for path in sorted(glob.glob("opponents_src/*.ipynb")):
    nbname = re.sub(r"[^A-Za-z0-9_]", "_", os.path.basename(path).replace(".ipynb", ""))[:26]
    with open(path, encoding="utf-8") as fh:
        nb = json.load(fh)

    for ci, cell in enumerate(nb["cells"]):
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        if len(src) < 200:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not names:
                continue

            # A) 压缩列表
            if isinstance(node.value, ast.List):
                try:
                    vals = [ast.literal_eval(e) for e in node.value.elts]
                except Exception:
                    continue
                if not vals or not all(isinstance(v, str) for v in vals):
                    continue
                if sum(len(v) for v in vals) < 2000:
                    continue
                blob = "".join(vals)
                for dn, dec in (("b64", base64.b64decode),
                                ("b85", base64.b85decode),
                                ("a85", base64.a85decode)):
                    got = None
                    try:
                        raw = dec(blob)
                    except Exception:
                        continue
                    for zn, zf in (("zlib", lambda b: zlib.decompress(b)),
                                   ("raw", lambda b: zlib.decompress(b, -15)),
                                   ("plain", lambda b: b)):
                        try:
                            d = zf(raw)
                        except Exception:
                            continue
                        if b"def " in d:
                            got = (d, f"{dn}/{zn}")
                            break
                    if got:
                        data, how = got
                        h = hashlib.sha256(data).hexdigest()
                        fn = f"{OUTDIR}/{nbname}_c{ci}_{h[:8]}.py"
                        with open(fn, "wb") as f2:
                            f2.write(data)
                        out.append(f"{os.path.basename(path)}")
                        out.append(f"   [压缩] cell{ci} {names[0]} {how} "
                                   f"{len(data):,}B  sha256={h[:12]} → {fn}")
                        saved[h[:12]] = len(data)
                        break

            # B) 明文 dict（如 TOP_AGENT_FILES）
            if isinstance(node.value, ast.Dict):
                try:
                    val = ast.literal_eval(node.value)
                except Exception:
                    continue
                if not isinstance(val, dict):
                    continue
                for k, v in val.items():
                    if not isinstance(v, str) or len(v) < 2000:
                        continue
                    if "def " not in v:
                        continue
                    h = hashlib.sha256(v.encode()).hexdigest()
                    fn = f"{OUTDIR}/{nbname}_c{ci}_{os.path.basename(str(k))}"
                    with open(fn, "w", encoding="utf-8") as f2:
                        f2.write(v)
                    out.append(f"{os.path.basename(path)}")
                    out.append(f"   [明文dict] cell{ci} {names[0]}['{k}'] "
                               f"{len(v):,}B  sha256={h[:12]} → {fn}")
                    saved[h[:12]] = len(v)

out.append("")
out.append(f"共保存 {len(saved)} 个 agent 到 {OUTDIR}/")

with open("_docx/pool_scan.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out))
