"""
地块预算实验：限制同时经营的地块数，测试"先铺满再扩张"的节奏是否更好。

动机
----
跨 18 位线上玩家的统计显示，高分组终局杂草 2.56 vs 低分组 8.22 —— 维护质量比规模重要。
ZZDW_（稳定打出 16k–30k）的做法是：**先在一个 5x5 内把 24 格铺满并维护到零杂草，
第 14 天才买地扩张**。而当前 main.py 在 day 1–3 就买地，背着更大的维护面积。

做法
----
给 main.py 注入一个 MAX_TILES 上限（默认不限制），在播种与买地环节都不超过它。
逐档扫描，看资金与杂草如何变化。

用法：
    python tile_budget.py --values 0,24,30,40,55 --episodes 6 --seed-base 15000
"""
import argparse
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")


def run_cfg(max_tiles, seeds, steps):
    for m in list(sys.modules):
        if m == "main":
            del sys.modules[m]
    import main

    orig = main._market_orders

    def patched(obs, me, priv, my_index):
        orders = orig(obs, me, priv, my_index)
        if max_tiles <= 0:
            return orders
        unlocked = sum(1 for r in me["tiles"] for t in r if t != "LOCKED")
        used = sum(1 for r in me["tiles"] for t in r
                   if isinstance(t, dict) and t.get("kind") in ("PLANT", "COOP", "PASTURE"))
        if used >= max_tiles:
            # 不再扩张，也不再补种子
            orders = [o for o in orders if o[0] not in ("BUY_LAND", "BUY_SEED")]
        return orders

    main._market_orders = patched

    outs = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": steps, "seed": seed}, debug=False)
        env.run([main.agent, "pass"])
        final = env.steps[-1][0]
        me = final.observation["farms"][0]
        tiles = me["tiles"]
        weeds = sum(1 for r in tiles for t in r
                    if isinstance(t, dict) and t.get("kind") == "WEED")
        plants = sum(1 for r in tiles for t in r
                     if isinstance(t, dict) and t.get("kind") == "PLANT")
        outs.append((float(final.reward or 0), weeds, plants))
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--values", default="0,24,30,40,55")
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=15000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    vals = [int(v) for v in args.values.split(",")]
    seeds = [args.seed_base + i for i in range(args.episodes)]

    lines = [f"地块预算扫描（对 pass，种子 {seeds[0]}–{seeds[-1]}）", "",
             f"{'上限':>6} {'平均资金':>11} {'最低':>11} {'平均杂草':>9} {'平均作物':>9}"]
    res = []
    for v in vals:
        outs = run_cfg(v, seeds, args.steps)
        money = [o[0] for o in outs]
        weeds = [o[1] for o in outs]
        plants = [o[2] for o in outs]
        res.append((v, statistics.mean(money)))
        lines.append(f"{('不限' if v == 0 else v):>6} {statistics.mean(money):>11,.0f} "
                     f"{min(money):>11,.0f} {statistics.mean(weeds):>9.1f} "
                     f"{statistics.mean(plants):>9.1f}")

    best = max(res, key=lambda r: r[1])
    lines.append("")
    lines.append(f"最佳 {'不限' if best[0]==0 else best[0]}（平均 ${best[1]:,.0f}）")

    with open("_docx/tile_budget.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
