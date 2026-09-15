"""
实验：把 FERTILIZE 加到候选 agent 上，看能否提升对局胜率。

依据（来自官方数据）：
  8 月 meta 施肥占比 1.2%，9 月 meta 1.3% —— 顶尖层在用。
  而我们所有候选（V38/C94/C95/KaitoV27/closer_cleo）施肥占比都是 0.0%。

安全含义（官方 README）：
  FERTILIZE 让一次性作物在 bonus window 内的每日产量加成翻倍
  （+2/天 而非 +1/天）；对持续作物，施肥+浇水当天产量翻倍（1 → 2）。
  施肥消耗 1 个 FERTILIZER（来自 COLLECT_FERTILIZER 或市场购买）。
  它不改变必须浇水的前提（basic needs first）。

做法：包装原 agent，在「生产动作」上加一层有界覆盖 ——
只把 PASS 或移动替换为 FERTILIZE，绝不打断种植/浇水/收获/喂食。
这与公开资料里 V14 的「有界覆盖」思路一致：不改主干，只补空档。
"""
import argparse
import contextlib
import io
import os
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}


def load(path):
    return get_last_callable(open(path, encoding="utf-8").read(), path=path)


def make_fert_wrapper(base, only_when_idle=True, max_per_game=40):
    """在 base agent 之上加施肥覆盖。

    规则：
      1. 若农场里存在「已浇水、且在 bonus window 内、尚未施肥」的作物，
         且本单位当前动作为 PASS 或移动，则改为 FERTILIZE。
      2. 不触碰任何生产动作。
    """
    state = {"used": 0}

    def agent(obs):
        act = base(obs)
        if not isinstance(act, dict) or state["used"] >= max_per_game:
            return act
        farm = obs["farms"][obs["player"]]
        shed = (obs.get("private") or {}).get("shed") or {}
        if shed.get("FERTILIZER", 0) <= 0:
            return act

        fx, fy = farm["farmer"]
        tile = farm["tiles"][fy][fx]
        if not (isinstance(tile, dict) and tile.get("kind") == "PLANT"):
            return act
        if not tile.get("watered_today"):
            return act
        if tile.get("fertilized_until_day", -1) >= obs.get("day", 0):
            return act
        day = obs.get("day", 0)
        crop = tile.get("crop")
        # 一次性作物：bonus window = ceil(max_yield_day/2) .. max_yield_day
        WIN = {"WHEAT": (2, 4), "CARROT": (2, 3), "MELON": (6, 12)}
        ONG = {"TOMATO", "STRAWBERRY"}
        age = day - tile.get("planted_day", day)
        ok = False
        if crop in WIN:
            lo, hi = WIN[crop]
            ok = lo <= age <= hi
        elif crop in ONG:
            ok = age >= 1
        if not ok:
            return act
        # 只覆盖 PASS 或移动
        f = act.get("farmer")
        if isinstance(f, list) and f:
            if f[0] == "PASS" or f[0] in MOVE:
                act = dict(act)
                act["farmer"] = ["FERTILIZE"]
                state["used"] += 1
        return act

    return agent


def run(base_path, use_wrapper, seeds, opponent="pass"):
    base = load(base_path)
    fn = make_fert_wrapper(base) if use_wrapper else base
    outs = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([fn, opponent])
        outs.append(float(env.steps[-1][0].reward or 0))
    return outs


ap = argparse.ArgumentParser()
ap.add_argument("--agent", default="candidates/V38.py")
ap.add_argument("--episodes", type=int, default=4)
ap.add_argument("--seed-base", type=int, default=980000)
args = ap.parse_args()

seeds = [args.seed_base + i for i in range(args.episodes)]
base_out = run(args.agent, False, seeds)
fert_out = run(args.agent, True, seeds)

out = [f"施肥实验：{os.path.basename(args.agent)}", f"种子 {seeds[0]}–{seeds[-1]}", ""]
out.append(f"{'种子':>10} {'原版':>12} {'加施肥':>12} {'差异':>12}")
out.append("-" * 50)
for s, a, b in zip(seeds, base_out, fert_out):
    out.append(f"{s:>10} {a:>12,.0f} {b:>12,.0f} {b-a:>+12,.0f}")
out.append("")
out.append(f"均值   原版 {statistics.mean(base_out):>10,.0f}   "
           f"加施肥 {statistics.mean(fert_out):>10,.0f}   "
           f"差 {statistics.mean(fert_out)-statistics.mean(base_out):>+10,.0f}")
w = sum(1 for a, b in zip(base_out, fert_out) if b > a)
out.append(f"加施肥占优的种子: {w}/{len(seeds)}")

text = "\n".join(out)
with open("_docx/fert_exp.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
