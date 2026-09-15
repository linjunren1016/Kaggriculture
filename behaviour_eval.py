"""
行为签名评测：直接测量「移动占比 / 浇水占比 / 终局杂草」。

为什么需要它
------------
跨 18 位线上玩家的统计显示，与高资金相关的是**维护质量（终局杂草）**，
而我的 Agent 行为签名与赢家差距最大的是**移动占比（71% vs 54%）**和
**浇水占比（13% vs 30%）**。但"资金"这个指标分辨不出这些差异
（前几轮的改动资金差异多为噪声）。

所以这个脚本直接测行为签名本身，作为改动的验收指标。

用法：
    python behaviour_eval.py --episodes 6 --seed-base 17000
"""
import argparse
import contextlib
import io
import statistics
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}

# 线上赢家的行为签名（来自 9 局回放里 ZZDW_ 的 6 次观测）
TARGET = {"move": 0.545, "water": 0.295, "pass": 0.030}


def profile(agent, opponent, seed, steps):
    env = make("kaggriculture",
               configuration={"episodeSteps": steps, "seed": seed}, debug=True)
    env.run([agent, opponent])
    final = env.steps[-1]

    ops = Counter()
    for st in env.steps:
        act = st[0].action
        if not act:
            continue
        f = act.get("farmer")
        if isinstance(f, list) and f:
            ops[f[0]] += 1
        for h in act.get("hands", []) or []:
            if isinstance(h, list) and h:
                ops[h[0]] += 1
    total = sum(ops.values())
    if not total:
        return None
    me = final[0].observation["farms"][0]
    tiles = me["tiles"]
    weeds = sum(1 for r in tiles for t in r
                if isinstance(t, dict) and t.get("kind") == "WEED")
    plants = sum(1 for r in tiles for t in r
                 if isinstance(t, dict) and t.get("kind") == "PLANT")
    return {
        "money": float(final[0].reward or 0),
        "move": sum(v for k, v in ops.items() if k in MOVE) / total,
        "water": ops.get("WATER", 0) / total,
        "pass": ops.get("PASS", 0) / total,
        "plant": ops.get("PLANT", 0) / total,
        "harvest": ops.get("HARVEST", 0) / total,
        "dig": ops.get("DIG", 0) / total,
        "weeds": weeds,
        "plants": plants,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="main.py")
    ap.add_argument("--opponent", default="pass")
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=17000)
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    rows = []
    for i in range(args.episodes):
        r = profile(args.agent, args.opponent, args.seed_base + i, args.steps)
        if r:
            rows.append(r)

    lines = [f"行为签名 {args.agent} vs {args.opponent}  "
             f"({len(rows)} 局, 种子 {args.seed_base}+) {args.tag}", ""]
    if not rows:
        lines.append("无有效对局")
    else:
        def m(k):
            return statistics.mean(r[k] for r in rows)

        lines.append(f"  平均资金    ${m('money'):>10,.0f}   "
                     f"最低 ${min(r['money'] for r in rows):>9,.0f}")
        lines.append(f"  移动占比    {m('move'):>9.1%}   目标 {TARGET['move']:.1%}")
        lines.append(f"  浇水占比    {m('water'):>9.1%}   目标 {TARGET['water']:.1%}")
        lines.append(f"  PASS 占比   {m('pass'):>9.1%}   目标 {TARGET['pass']:.1%}")
        lines.append(f"  种植 / 收获 {m('plant'):>9.1%} / {m('harvest'):.1%}")
        lines.append(f"  终局杂草    {m('weeds'):>9.1f}   "
                     f"（低分组 8.22 / 高分组 2.56）")
        lines.append(f"  终局作物    {m('plants'):>9.1f}")

        # 与目标的偏差（越小越好，仅作方向参考）
        gap = abs(m("move") - TARGET["move"]) + abs(m("water") - TARGET["water"])
        lines.append("")
        lines.append(f"  行为签名偏差（越小越接近线上赢家）: {gap:.3f}")

    text = "\n".join(lines)
    with open("_docx/behaviour.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
