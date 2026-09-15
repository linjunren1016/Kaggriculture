"""检查下载的 notebook：找出 agent 入口、动作表等可复现成分。"""
import glob
import json
import os
import re

out = []
for path in sorted(glob.glob("opponents_src/*.ipynb")):
    out.append("=" * 78)
    out.append(os.path.basename(path))
    with open(path, encoding="utf-8") as fh:
        nb = json.load(fh)

    cells = nb.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    md_cells = [c for c in cells if c.get("cell_type") == "markdown"]
    out.append(f"  cells: {len(cells)} (code {len(code_cells)}, md {len(md_cells)})")

    all_code = "\n".join("".join(c.get("source", [])) for c in code_cells)

    # 找 agent 定义
    defs = re.findall(r"^\s*def\s+(\w+)\s*\(", all_code, re.M)
    out.append(f"  函数定义: {defs[:20]}")

    # 找 agent = 赋值 / 入口
    assigns = re.findall(r"^\s*(agent|my_agent|policy)\s*=", all_code, re.M)
    out.append(f"  agent 赋值: {set(assigns)}")

    # 找动作表类资源
    for kw in ("_TABLE", "ACTION_TABLE", "action_table", "ROUTE", "route",
               "STEPS", "PLAN", "plan"):
        if kw in all_code:
            n = all_code.count(kw)
            out.append(f"  含 {kw}: {n} 次")

    # 找关键机制
    for kw in ("FERTILIZE", "BUY_ANIMAL", "BUILD_PASTURE", "HIRE", "BUY_LAND",
               "unlocked_shops", "Impact", "urgency", "DIG", "MELON"):
        if kw in all_code:
            out.append(f"  提到 {kw}: {all_code.count(kw)} 次")

    # 动作表长度线索：找形如 {0: ...} 或 [ ... ] * 719
    m = re.search(r"(\d{3})\s*#.*step", all_code)
    out.append(f"  代码总字符: {len(all_code)}")

    # 前 3 个 code cell 的开头
    out.append("  前 2 个 code cell 开头:")
    for c in code_cells[:2]:
        src = "".join(c.get("source", []))
        for line in src.splitlines()[:8]:
            out.append("    " + line[:100])
        out.append("    ---")
    out.append("")

with open("_docx/notebooks.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out[:120]))
