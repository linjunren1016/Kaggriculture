"""
从回放 parquet 中提取指定 episode 的动作序列，生成本地可运行的 agent。

这是本轮的核心手段：把「真实高 rating 的线上 agent」还原成单文件 agent，
从而能在本地直接对打验证（而不是只看它们的统计特征）。

用法：
    python replay_to_agent.py --targets _docx/top_targets.csv --limit 8
"""
import argparse
import csv
import glob
import json
import os
import sys

sys.path.insert(0, ".")


TEMPLATE = '''"""
从公开回放还原的线上 agent。

来源：Kaggle 公开数据集 georgymamarin/kaggriculture-episodes 的 replay parquet。
episode {ep}  座位 {seat}  该局 rating_after={rating}
该局终局资金 {bank}

这是「固定动作表」还原：按 step 直接回放当时提交的动作序列。
它精确复现该 agent 在那张地图上的行为，但换地图后退化（固定序列的固有弱点）。
仅用于本地评测与对比分析。
"""

_TABLE = {table}


def _norm(op):
    return [op] if isinstance(op, str) else list(op)


def agent(obs):
    step = obs.get("step", 0)
    e = _TABLE.get(step)
    if e is None:
        return {{"farmer": ["PASS"], "hands": [], "market": []}}
    return {{"farmer": _norm(e["farmer"]),
             "hands": [_norm(h) for h in e["hands"]],
             "market": [list(m) for m in e["market"]]}}
'''


def norm_action(a):
    if not isinstance(a, dict):
        return None
    f = a.get("farmer")
    if isinstance(f, str):
        f = [f]
    hands = [h if isinstance(h, list) else [h] for h in (a.get("hands") or [])]
    market = [list(m) for m in (a.get("market") or [])]
    return {"farmer": f or ["PASS"], "hands": hands, "market": market}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="_docx/top_targets.csv")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--outdir", default="opponents_src/top")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    targets = []
    with open(args.targets, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            targets.append(row)
    targets = targets[:args.limit]
    print(f"目标 {len(targets)} 个")
    want = {t["episode_id"]: t for t in targets}

    import pyarrow.parquet as pq
    found = {}
    files = sorted(glob.glob("episodes/replays_*.parquet"))
    for f in files:
        if len(found) == len(want):
            break
        pf = pq.ParquetFile(f)
        for batch in pf.iter_batches(batch_size=256, columns=["episode_id", "replay_json"]):
            ids = batch.column("episode_id").to_pylist()
            js = batch.column("replay_json").to_pylist()
            for eid, raw in zip(ids, js):
                s = str(eid)
                if s in want and s not in found:
                    found[s] = raw
            if len(found) == len(want):
                break
        print(f"  {f}: 已找到 {len(found)}/{len(want)}")

    out = []
    for eid, t in want.items():
        raw = found.get(eid)
        if raw is None:
            out.append(f"ep {eid}: 未在回放中找到")
            continue
        d = json.loads(raw) if isinstance(raw, str) else raw
        steps = d.get("steps", [])
        seat = int(t["seat"])
        table = {}
        for i, st in enumerate(steps):
            if seat < len(st):
                na = norm_action(st[seat].get("action"))
                if na:
                    table[i] = na
        fn = os.path.join(args.outdir, f"top_{eid}_s{seat}.py")
        src = TEMPLATE.format(ep=eid, seat=seat, rating=t["rating"],
                              bank=t["bank"], table=repr(table))
        with open(fn, "w", encoding="utf-8") as fh:
            fh.write(src)
        out.append(f"ep {eid} seat {seat}: {len(table)} 步动作 → {fn} "
                   f"(rating {t['rating']}, bank {t['bank']})")

    text = "\n".join(out)
    with open("_docx/replay_agents.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
