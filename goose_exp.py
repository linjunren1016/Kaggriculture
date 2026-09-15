"""
实验：给 V38 补鹅（GOOSE）。

唯一明确的规则差异：9 月 12 个高分 agent 终局都养 2 只鹅（0-2 只，均值 2.0），
而 V38 / C94 的鹅都是 0。它们有 16 个畜舍（含 2 个 COOP 用来放鹅），
V38 只有 15.3 个且全是 PASTURE。

背景（官方 crop_economics）：鹅成本 300、蛋基价 50、日产出 2.0 单位、
gross 100/格/天、EGG 有 5 家商店需求（崩盘前可卖 >6000 个）——
从"商店需求"看，蛋是最抗跌的品类之一。

做法：在 V38 之上加一层「补鹅」覆盖 ——
若畜舍未满且资金充裕，则 BUY_ANIMAL GOOSE + BUILD_COOP，
并把鹅放到空 coop 上。只补空档，不改其它决策。

不改 V38 源文件（保持哈希）。
"""
import argparse
import contextlib
import importlib.util
import io
import statistics
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")


def load_v38():
    spec = importlib.util.spec_from_file_location("v38g", "candidates/V38.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_goose_wrapper(base, target_geese=2, buy_from_day=2):
    """在 base 之上补鹅：买鹅 + 建鸡舍 + 放置。"""
    def agent(obs):
        act = base(obs)
        if not isinstance(act, dict):
            return act
        try:
            day = obs.get("day", 0)
            if day < buy_from_day or day > 26:
                return act
            farm = obs["farms"][obs["player"]]
            tiles = farm["tiles"]
            geese = 0
            empty_coop = 0
            owned_coop = 0
            for row in tiles:
                for t in row:
                    if isinstance(t, dict) and t.get("kind") == "COOP":
                        owned_coop += 1
                        if t.get("animal") == "GOOSE":
                            geese += 1
                        elif not t.get("animal"):
                            empty_coop += 1
            if geese >= target_geese:
                return act
            shed = (obs.get("private") or {}).get("shed") or {}
            market = list(act.get("market") or [])
            money = farm.get("money", 0)
            # 1) 需要的话买鹅（进仓库）
            have_goose = shed.get("GOOSE", 0)
            if geese + have_goose < target_geese and money > 300 + 1500 \
                    and len(market) < 10:
                market.append(["BUY_ANIMAL", "GOOSE", 1])
            # 2) 没有空 coop 且手里有鹅 → 建 coop
            fx, fy = farm["farmer"]
            tile = tiles[fy][fx]
            if have_goose > 0 and empty_coop == 0 and tile is None:
                act = dict(act)
                act["farmer"] = ["BUILD_COOP"]
                act["market"] = market
                return act
            act = dict(act)
            act["market"] = market
        except Exception:
            pass
        return act
    return agent


def run(mod, wrapper, seeds):
    fn = wrapper(mod.agent) if wrapper else mod.agent
    money, geese, coins = [], [], []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([fn, "pass"])
        farm = env.steps[-1][0].observation["farms"][0]
        g = c = 0
        for row in farm["tiles"]:
            for t in row:
                if isinstance(t, dict):
                    if t.get("animal") == "GOOSE":
                        g += 1
                    if isinstance(t, dict) and t.get("kind") == "COOP":
                        c += 1
        money.append(float(env.steps[-1][0].reward or 0))
        geese.append(g)
        coins.append(c)
    return money, geese, coins


ap = argparse.ArgumentParser()
ap.add_argument("--episodes", type=int, default=5)
ap.add_argument("--seed-base", type=int, default=1210000)
args = ap.parse_args()

seeds = [args.seed_base + i for i in range(args.episodes)]
m0 = load_v38()
base_money, base_geese, _ = run(m0, False, seeds)
m1 = load_v38()
gos_money, gos_geese, gos_coop = run(m1, make_goose_wrapper, seeds)

out = [f"补鹅实验（种子 {seeds[0]}–{seeds[-1]}）",
       "9 月高分终局养 2 只鹅；V38 为 0", ""]
out.append(f"{'种子':>10} {'V38':>12} {'加鹅':>12} {'差异':>12} {'鹅数':>5}")
out.append("-" * 56)
for s, a, b, g in zip(seeds, base_money, gos_money, gos_geese):
    out.append(f"{s:>10} {a:>12,.0f} {b:>12,.0f} {b-a:>+12,.0f} {g:>5}")
out.append("")
out.append(f"均值   V38 {statistics.mean(base_money):>11,.0f}   "
           f"加鹅 {statistics.mean(gos_money):>11,.0f}   "
           f"差 {statistics.mean(gos_money)-statistics.mean(base_money):>+11,.0f}")
w = sum(1 for a, b in zip(base_money, gos_money) if b > a)
out.append(f"加鹅占优 {w}/{len(seeds)}   终局鹅数均值 {statistics.mean(gos_geese):.1f}")

text = "\n".join(out)
with open("_docx/goose_exp.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
