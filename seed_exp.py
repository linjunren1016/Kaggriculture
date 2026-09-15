"""
BUY_SEED 对齐实验。

依据（官方 9 月 meta）：BUY_SEED 177.2 次/局；V38 只有 ~101 次（低 43%）。
9 月 12 个高分 agent 的 BUY_SEED 集中在 187-190（除个别 52/114）。

做法：在 V38 之上加一层「种子补足」覆盖 ——
按目标作物配比检查「已种 + 库存」，不足则下 BUY_SEED 单。
只补空缺，不动其它市场订单；总订单数受 10 条上限约束。

不改 V38 源文件（保持哈希可验证）。
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

# 目标配比（参考 9 月 meta 的植株构成）
TARGETS = {"WHEAT": 130, "STRAWBERRY": 40, "MELON": 20, "CARROT": 10}


def load_v38():
    spec = importlib.util.spec_from_file_location("v38m", "candidates/V38.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_seed_topup(base):
    def agent(obs):
        act = base(obs)
        if not isinstance(act, dict):
            return act
        try:
            farm = obs["farms"][obs["player"]]
            priv = obs.get("private") or {}
            seeds = priv.get("seeds") or {}
            tiles = farm["tiles"]
            counts = Counter()
            empty = 0
            for row in tiles:
                for t in row:
                    if isinstance(t, dict) and t.get("kind") == "PLANT":
                        counts[t.get("crop")] += 1
                    elif t is None:
                        empty += 1
            if empty <= 0:
                return act
            market = list(act.get("market") or [])
            have_seed = sum(v for v in seeds.values())
            if have_seed >= empty:
                return act
            # 找缺口最大的作物
            best, best_gap = None, 0
            for crop, want in TARGETS.items():
                gap = want - (counts.get(crop, 0) + seeds.get(crop, 0))
                if gap > best_gap:
                    best, best_gap = crop, gap
            if not best:
                return act
            n = min(best_gap, max(1, empty - have_seed), 6)
            if len(market) >= 10:
                return act
            market.append(["BUY_SEED", best, n])
            act = dict(act)
            act["market"] = market
        except Exception:
            pass
        return act

    return agent


def run(mod, wrapper, seeds):
    fn = wrapper(mod.agent) if wrapper else mod.agent
    sells, buys, money = [], [], []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([fn, "pass"])
        s = b = 0
        for st in env.steps:
            for o in ((st[0].action or {}).get("market") or []):
                if o and o[0] == "SELL":
                    s += 1
                elif o and o[0] == "BUY_SEED":
                    b += 1
        sells.append(s)
        buys.append(b)
        money.append(float(env.steps[-1][0].reward or 0))
    return statistics.mean(sells), statistics.mean(buys), money


ap = argparse.ArgumentParser()
ap.add_argument("--episodes", type=int, default=5)
ap.add_argument("--seed-base", type=int, default=991000)
args = ap.parse_args()

seeds = [args.seed_base + i for i in range(args.episodes)]
out = [f"BUY_SEED 补足实验（种子 {seeds[0]}–{seeds[-1]}）",
       "目标：BUY_SEED≈177/局（9 月 meta）；V38 基线约 101", ""]

base_mod = load_v38()
bs, bb, bm = run(base_mod, False, seeds)

top_mod = load_v38()
ts, tb, tm = run(top_mod, make_seed_topup, seeds)

out.append(f"{'配置':<14} {'SELL/局':>9} {'BUY_SEED/局':>12} {'平均资金':>12} {'最低':>12}")
out.append("-" * 56)
out.append(f"{'V38 基线':<14} {bs:>9.1f} {bb:>12.1f} {statistics.mean(bm):>12,.0f} {min(bm):>12,.0f}")
out.append(f"{'加种子补足':<14} {ts:>9.1f} {tb:>12.1f} {statistics.mean(tm):>12,.0f} {min(tm):>12,.0f}")
out.append("")
out.append(f"资金差 {statistics.mean(tm)-statistics.mean(bm):>+,.0f}   "
           f"加补足占优的种子 {sum(1 for a,b in zip(tm,bm) if a>b)}/{len(seeds)}")
out.append("")
out.append("逐种子：")
for s, a, b in zip(seeds, bm, tm):
    out.append(f"  {s}: 基线 {a:>11,.0f}   加补足 {b:>11,.0f}   {b-a:>+11,.0f}")

text = "\n".join(out)
with open("_docx/seed_exp.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
