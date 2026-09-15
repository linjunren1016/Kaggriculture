"""
分析 Kaggle 线上回放：对比我方与对手的开局和运营。

回放里能看到：
  info.Agents[].Name  对手名字（可用来识别是谁打赢了我们）
  info.seed           地图种子（可用本地环境还原同一局）
  rewards             终局资金
  steps[i][p]         action / observation / reward

重点看开局（前 100 步）和土地/雇工/作物的扩张节奏，找出结构性差异。
"""
import glob
import json
import os
import sys
from collections import Counter

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}


def summarize(path, out):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)

    info = d.get("info", {})
    names = [a.get("Name") for a in info.get("Agents", [])]
    teams = info.get("TeamNames", [])
    rewards = d.get("rewards", [])
    seed = info.get("seed")

    out.append("=" * 78)
    out.append(f"回放 {os.path.basename(path)}")
    out.append(f"  episode   {info.get('EpisodeId')}")
    out.append(f"  seed      {seed}")
    out.append(f"  agents    {names}")
    out.append(f"  teams     {teams}")
    out.append(f"  rewards   {rewards}")
    if len(rewards) == 2:
        win = "平局" if rewards[0] == rewards[1] else (
            f"玩家0 胜" if rewards[0] > rewards[1] else f"玩家1 胜")
        out.append(f"  结果      {win}   分差 {abs(rewards[0]-rewards[1]):,.0f}")

    steps = d["steps"]

    # 每个玩家的开局动作序列（前 40 步）
    for p in (0, 1):
        label = f"{names[p] if p < len(names) else '?'} (玩家{p})"
        out.append("")
        out.append(f"--- {label} ---")

        # 市场订单统计
        market = Counter()
        first_ops = []
        for i, st in enumerate(steps):
            if i >= len(steps):
                break
            entry = st[p]
            act = entry.get("action")
            if not act:
                continue
            for m in act.get("market", []) or []:
                market[m[0]] += 1
            if i < 40:
                for m in act.get("market", []) or []:
                    first_ops.append(f"step{i}: {' '.join(str(x) for x in m)}")
                f = act.get("farmer")
                if i < 16 and f:
                    first_ops.append(f"step{i}: farmer {' '.join(str(x) for x in f)}")

        out.append("  市场订单统计: " +
                   ", ".join(f"{k}×{v}" for k, v in market.most_common()))
        out.append("  开局动作（前 40 步的市场 + 前 16 步的农民）:")
        for line in first_ops[:24]:
            out.append("    " + line)

        # 关键节点：土地 / 雇工 / 作物 / 资金
        out.append("  运营节奏:")
        out.append(f"    {'day':>4} {'money':>10} {'土地':>5} {'雇工':>5} "
                   f"{'作物':>5} {'杂草':>5} {'空地':>5}")
        for day in (0, 2, 4, 6, 8, 12, 16, 20, 24, 28, 29):
            idx = min(day * 24, len(steps) - 1)
            obs = steps[idx][p].get("observation", {})
            farms = obs.get("farms")
            if not farms:
                continue
            farm = farms[p]
            tiles = farm.get("tiles", [])
            plants = sum(1 for r in tiles for t in r
                         if isinstance(t, dict) and t.get("kind") == "PLANT")
            weeds = sum(1 for r in tiles for t in r
                        if isinstance(t, dict) and t.get("kind") == "WEED")
            empty = sum(1 for r in tiles for t in r if t is None)
            out.append(f"    {day:>4} {farm.get('money', 0):>10,.0f} "
                       f"{len(farm.get('unlocked_quadrants', [])):>4}/4 "
                       f"{len(farm.get('hands', [])):>5} {plants:>5} {weeds:>5} {empty:>5}")

        # 终局地块构成
        obs = steps[-1][p].get("observation", {})
        farms = obs.get("farms")
        if farms:
            tiles = farms[p].get("tiles", [])
            crops = Counter(t.get("crop") for r in tiles for t in r
                            if isinstance(t, dict) and t.get("kind") == "PLANT")
            animals = Counter(t.get("animal") for r in tiles for t in r
                              if isinstance(t, dict) and t.get("animal"))
            out.append(f"  终局作物: {dict(crops)}")
            out.append(f"  终局牲畜: {dict(animals)}")
            shed = obs.get("private", {}).get("shed", {})
            out.append(f"  终局仓库: {dict((k, v) for k, v in shed.items() if v)}")


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "replays/episode-*-replay.json"
    out = []
    for path in sorted(glob.glob(pattern)):
        summarize(path, out)
        out.append("")
    text = "\n".join(out)
    with open("_docx/online_replay_analysis.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"分析了 {len(glob.glob(pattern))} 个回放")
    print(text[:2000])


if __name__ == "__main__":
    main()
