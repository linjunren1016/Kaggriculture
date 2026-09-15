"""
完整跑一局 Kaggriculture（本地环境，720 回合），并导出回放文件。

回放 JSON 可以用竞赛页面上内嵌的浏览器版可视化器打开，直接看这局是怎么打的。

用法：
    python run_episode.py                        # 默认 starter vs random
    python run_episode.py --p0 main.py --p1 starter
    python run_episode.py --seed 123 --out replays/my_game.json
"""
import argparse
import contextlib
import io
import json
import os
import sys
import time

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def describe(obs, label):
    farm = obs["farms"][obs["player"]]
    tiles = farm["tiles"]
    plants = sum(1 for r in tiles for t in r
                 if isinstance(t, dict) and t.get("kind") == "PLANT")
    weeds = sum(1 for r in tiles for t in r
                if isinstance(t, dict) and t.get("kind") == "WEED")
    structures = sum(1 for r in tiles for t in r
                     if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"))
    animals = sum(1 for r in tiles for t in r
                  if isinstance(t, dict) and t.get("animal"))
    shed = {k: v for k, v in obs["private"]["shed"].items() if v}
    return (f"  {label:<10} money=${farm['money']:>9,.0f}  "
            f"hands={len(farm.get('hands', []))}  "
            f"土地={len(farm.get('unlocked_quadrants', []))}/4  "
            f"作物={plants:>2} 杂草={weeds:>2} 畜舍={structures} 牲畜={animals}  "
            f"仓库={shed if shed else '{}'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p0", default="starter")
    ap.add_argument("--p1", default="random")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--out", default=os.path.join("replays", "episode.json"))
    args = ap.parse_args()

    print(f"Kaggriculture 对局：玩家0 = {args.p0}  玩家1 = {args.p1}")
    print(f"seed = {args.seed}   回合数 = {args.steps}\n")

    env = make("kaggriculture",
               configuration={"episodeSteps": args.steps, "seed": args.seed},
               debug=False)

    # 起手状态
    states = env.reset()
    print("起手状态：")
    print(describe(states[0]["observation"], "玩家0"))
    print(describe(states[1]["observation"], "玩家1"))
    print()

    # 跑完整局
    t0 = time.time()
    env.run([args.p0, args.p1])
    elapsed = time.time() - t0

    final = env.steps[-1]
    print(f"对局结束，用时 {elapsed:.1f} 秒，共 {len(env.steps)} 个记录状态。\n")

    print("终局状态：")
    print(describe(final[0]["observation"], "玩家0"))
    print(describe(final[1]["observation"], "玩家1"))
    print()

    print("结果：")
    r0 = float(final[0].reward or 0.0)
    r1 = float(final[1].reward or 0.0)
    print(f"  {args.p0}（座位0）：{r0:,.0f}   状态={final[0].status}")
    print(f"  {args.p1}（座位1）：{r1:,.0f}   状态={final[1].status}")
    if r0 > r1:
        winner = f"玩家0（{args.p0}）"
    elif r1 > r0:
        winner = f"玩家1（{args.p1}）"
    else:
        winner = "平局"
    print(f"  => 胜者：{winner}   分差 {abs(r0 - r1):,.0f}")

    # 中途关键节点，便于观察生产链建立过程
    print("\n过程中的关键节点：")
    for step in (0, 96, 240, 480, 719):
        if step < len(env.steps):
            obs = env.steps[step][0].observation
            print(f"  day {obs['day']:>2} hour {obs['hour']:>2} | "
                  f"p0=${obs['farms'][0]['money']:>9,.0f}  "
                  f"p1=${obs['farms'][1]['money']:>9,.0f}")

    # 导出回放
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(env.toJSON(), fh)
    size_mb = os.path.getsize(args.out) / 1024 / 1024
    print(f"\n回放已导出：{args.out}  ({size_mb:.1f} MB)")
    print("可用竞赛页面内嵌的可视化器打开这个 JSON 观看整局。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
