"""摸清 Kaggle 线上回放 JSON 的结构（与本地 env.toJSON() 可能不同）。"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else \
    "replays/episode-109170440-replay.json"

with open(path, encoding="utf-8") as fh:
    d = json.load(fh)

out = []


def show(obj, name, depth=0):
    pad = "  " * depth
    if isinstance(obj, dict):
        out.append(f"{pad}{name}: dict, {len(obj)} keys")
        for k, v in list(obj.items())[:20]:
            if isinstance(v, (dict, list)):
                show(v, k, depth + 1)
            else:
                s = str(v)
                out.append(f"{pad}  {k} = {s[:70]}")
    elif isinstance(obj, list):
        out.append(f"{pad}{name}: list, len={len(obj)}")
        if obj:
            show(obj[0], f"{name}[0]", depth + 1)


show(d, "root")

# 关键字段细节
out.append("")
out.append("=== 关键字段 ===")
for key in ("id", "name", "configuration", "info"):
    if key in d:
        out.append(f"{key}: {json.dumps(d[key])[:300]}")

if "steps" in d:
    out.append("")
    out.append(f"steps 长度: {len(d['steps'])}")
    st0 = d["steps"][0]
    out.append(f"steps[0] 类型: {type(st0).__name__}, 长度 {len(st0) if hasattr(st0,'__len__') else '-'}")
    if isinstance(st0, list) and st0:
        out.append(f"steps[0][0] keys: {list(st0[0].keys())}")
        obs = st0[0].get("observation", {})
        out.append(f"observation keys: {list(obs.keys()) if isinstance(obs, dict) else type(obs)}")

with open("_docx/replay_structure.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
