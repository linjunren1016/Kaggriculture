"""读取参考 agent 天梯的元数据：manifest、基线联盟、价格曲线、作物经济学。"""
import csv
import os

FILES = ["agents_manifest.csv", "baseline_league.csv",
         "price_curves.csv", "crop_economics.csv"]
BASE = "opponents_src"

out = []
for fn in FILES:
    p = os.path.join(BASE, fn)
    out.append("=" * 78)
    out.append(fn)
    if not os.path.exists(p):
        out.append("  (不存在)")
        continue
    with open(p, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        out.append("  (空)")
        continue
    out.append(f"  列: {rows[0]}")
    out.append(f"  行数: {len(rows)-1}")
    for r in rows[1:20]:
        out.append("   " + " | ".join(c[:34] for c in r))
    if len(rows) > 21:
        out.append(f"   ... 另有 {len(rows)-21} 行")
    out.append("")

with open("_docx/ladder_meta.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("\n".join(out))
