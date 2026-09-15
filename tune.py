"""
Parameter sweep for the Kaggriculture agent.

The agent reads its tunables from module globals, so we can import it once and
mutate those globals between episodes instead of editing the file. Each config
is scored over several seeded full seasons against a fixed opponent.

Usage:
    python tune.py --episodes 3 --opponents starter
"""
import argparse
import contextlib
import io
import itertools
import json
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")
import main as A


def run(cfg, opponent, seed, steps):
    for key, value in cfg.items():
        setattr(A, key, value)
    env = make("kaggriculture",
               configuration={"episodeSteps": steps, "seed": seed}, debug=False)
    env.run([A.agent, opponent])
    final = env.steps[-1]
    return float(final[0].reward or 0.0), float(final[1].reward or 0.0)


def score(cfg, opponents, episodes, steps):
    mine, theirs, wins = [], [], 0
    for opp in opponents:
        for i in range(episodes):
            m, o = run(cfg, opp, 1000 + i, steps)
            mine.append(m)
            theirs.append(o)
            if m > o:
                wins += 1
    return {
        "mean": round(statistics.mean(mine), 1),
        "min": round(min(mine), 1),
        "wins": wins,
        "n": len(mine),
        "opp_mean": round(statistics.mean(theirs), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=2)
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--opponents", nargs="*", default=["starter"])
    args = ap.parse_args()

    grid = {
        "HIRE_CAP": [3, 6, 8],
        "FEED_PICKUP_BATCH": [6, 12],
        "MAX_LIVESTOCK": [4, 8, 14],
    }
    # MAX_LIVESTOCK may not exist yet; add it so the sweep can control it.
    if not hasattr(A, "MAX_LIVESTOCK"):
        A.MAX_LIVESTOCK = 12

    keys = list(grid)
    results = []
    for combo in itertools.product(*(grid[k] for k in keys)):
        cfg = dict(zip(keys, combo))
        res = score(cfg, args.opponents, args.episodes, args.steps)
        res["config"] = cfg
        results.append(res)
        print(f"{cfg} -> mean=${res['mean']:<9} min=${res['min']:<9} "
              f"wins={res['wins']}/{res['n']} opp=${res['opp_mean']}")

    results.sort(key=lambda r: r["mean"], reverse=True)
    print("\n=== best 5 ===")
    for r in results[:5]:
        print(f"  ${r['mean']:<9} {r['config']}  ({r['wins']}/{r['n']} wins)")
    with open("tune_results.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print("wrote tune_results.json")


if __name__ == "__main__":
    main()
