"""
深度对比：我方与线上对手的动作分布与运营节奏。

关注：
  1. 雇工是否真的为 0（用原始字段核对，而不是只看采样点）
  2. 动作分布差异（浇水 / 移动 / 种植 / 收获 / 挖草 / 施肥）
  3. 土地扩张时点
  4. 施肥（FERTILIZE）使用 —— 高分方案是否在用
"""
import glob
import json
import os
import sys
from collections import Counter

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}


def hands_at(steps, p, idx):
    """用原始字段核对该步的雇工数。"""
    obs = steps[idx][p].get("observation", {}) or {}
    farms = obs.get("farms")
    if not farms:
        return None
    return len(farms[p].get("hands", []) or [])


def analyze(path, out):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    info = d.get("info", {})
    names = [a.get("Name") for a in info.get("Agents", [])]
    teams = info.get("TeamNames", []) or names
    rewards = d.get("rewards", [])
    steps = d["steps"]

    out.append("=" * 78)
    out.append(f"{os.path.basename(path)}   seed={info.get('seed')}")
    out.append(f"  {teams[0]}={rewards[0]:,.0f}  vs  {teams[1]}={rewards[1]:,.0f}")

    for p in (0, 1):
        label = teams[p] if p < len(teams) else f"p{p}"
        ops = Counter()
        market = Counter()
        fert_ops = 0
        for st in steps:
            act = st[p].get("action")
            if not act:
                continue
            f = act.get("farmer")
            if isinstance(f, list) and f:
                ops[f[0]] += 1
                if f[0] == "FERTILIZE":
                    fert_ops += 1
            for h in act.get("hands", []) or []:
                if isinstance(h, list) and h:
                    ops[h[0]] += 1
                    if h[0] == "FERTILIZE":
                        fert_ops += 1
            for m in act.get("market", []) or []:
                market[m[0]] += 1

        total = sum(ops.values())
        move = sum(v for k, v in ops.items() if k in MOVE)
        out.append("")
        out.append(f"--- {label} ---  终局 ${rewards[p]:,.0f}")
        # 雇工核对
        sample = [hands_at(steps, p, i) for i in (0, 24, 120, 300, 600, 719)]
        out.append(f"  雇工数@若干步 {sample}")
        out.append(f"  动作总数 {total}   移动占比 {move/total:.1%}" if total else "  无动作")
        top = ", ".join(f"{k}×{v}({v/total:.0%})" for k, v in ops.most_common(8))
        out.append(f"  动作分布: {top}")
        out.append(f"  FERTILIZE 次数: {fert_ops}")
        out.append(f"  市场: {', '.join(f'{k}×{v}' for k, v in market.most_common())}")

        # 土地扩张时点
        land_day = {}
        for i, st in enumerate(steps):
            obs = st[p].get("observation", {}) or {}
            farms = obs.get("farms")
            if not farms:
                continue
            n = len(farms[p].get("unlocked_quadrants", []) or [])
            day = i // 24
            if n not in land_day:
                land_day[n] = day
        out.append(f"  土地解锁时点(块数->首次出现的天): {land_day}")


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "replays/episode-*-replay.json"
    out = []
    for path in sorted(glob.glob(pattern)):
        analyze(path, out)
    text = "\n".join(out)
    with open("_docx/deep_compare.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
