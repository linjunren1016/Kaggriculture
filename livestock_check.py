"""
核实 V38 的牲畜放置效率：它买了多少、建了多少畜舍、最终放上几只。

对照 9 月高分 agent：BUY_ANIMAL 12.4 / BUILD_PASTURE 15.0 / 终局牲畜 16.6
"""
import contextlib
import io
import statistics
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


def profile(path, seeds, label, out):
    fn = load(path)
    res = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([fn, "pass"])
        ops = Counter()
        market = Counter()
        for st in env.steps:
            a = st[0].action or {}
            f = a.get("farmer")
            if isinstance(f, list) and f:
                ops[f[0]] += 1
            for h in a.get("hands") or []:
                if isinstance(h, list) and h:
                    ops[h[0]] += 1
            for m in a.get("market") or []:
                if m:
                    market[m[0]] += 1
        farm = env.steps[-1][0].observation["farms"][0]
        tiles = farm["tiles"]
        animals = Counter()
        structs = 0
        for row in tiles:
            for t in row:
                if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"):
                    structs += 1
                    if t.get("animal"):
                        animals[t["animal"]] += 1
        res.append({
            "BUY_ANIMAL": market.get("BUY_ANIMAL", 0),
            "BUILD_PASTURE": ops.get("BUILD_PASTURE", 0),
            "BUILD_COOP": ops.get("BUILD_COOP", 0),
            "PLACE": ops.get("PLACE", 0),
            "CARE": ops.get("CARE", 0),
            "FEED": ops.get("FEED", 0),
            "PICKUP": ops.get("PICKUP", 0),
            "COLLECT_FERT": ops.get("COLLECT_FERTILIZER", 0),
            "structs": structs,
            "animals": sum(animals.values()),
            "cow": animals.get("COW", 0),
            "sheep": animals.get("SHEEP", 0),
            "goose": animals.get("GOOSE", 0),
            "land": len(farm.get("unlocked_quadrants", []) or []),
            "money": float(env.steps[-1][0].reward or 0),
        })
    out.append(f"--- {label} ---")
    keys = ["BUY_ANIMAL", "BUILD_PASTURE", "BUILD_COOP", "PLACE", "CARE", "FEED",
            "PICKUP", "COLLECT_FERT", "structs", "animals", "cow", "sheep",
            "goose", "land", "money"]
    for k in keys:
        out.append(f"    {k:<14} {statistics.mean(r[k] for r in res):>9.1f}")
    return res


SEEDS = [1200000, 1200001, 1200002]
out = ["V38 的牲畜链 vs 9 月高分标准", "",
       "9 月高分（12 局均值）：BUY_ANIMAL 12.4 / BUILD_PASTURE 15.0 / "
       "CARE 405 / FEED 358 / PICKUP 199 / 终局牲畜 16.6（7牛8羊2鹅）/ 象限 3.2",
       ""]
profile("candidates/V38.py", SEEDS, "V38", out)
out.append("")
profile("candidates/C94.py", SEEDS, "C94", out)

text = "\n".join(out)
with open("_docx/livestock_check.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
