"""
Local benchmark harness for the Kaggriculture agent.

Runs the submission agent against each built-in opponent over N seeded episodes
and reports money statistics. Seeded episodes make the comparison repeatable,
which matters when the numbers go into a written report.

Usage:
    python benchmark.py                # 10 episodes vs each opponent
    python benchmark.py --episodes 20
    python benchmark.py --agent other.py
"""
import argparse
import contextlib
import io
import json
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

OPPONENTS = ["pass", "random", "starter"]


def run_episode(agent_path, opponent, seed, steps):
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": steps, "seed": seed},
        debug=False,
    )
    env.run([agent_path, opponent])
    final = env.steps[-1]
    mine = final[0].reward or 0.0
    theirs = final[1].reward or 0.0
    return float(mine), float(theirs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="main.py")
    ap.add_argument("--episodes", type=int, default=10)
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--opponents", nargs="*", default=OPPONENTS)
    args = ap.parse_args()

    summary = {}
    for opp in args.opponents:
        mine_scores, opp_scores, wins, losses, ties = [], [], 0, 0, 0
        for i in range(args.episodes):
            seed = 1000 + i
            try:
                m, o = run_episode(args.agent, opp, seed, args.steps)
            except Exception as exc:                      # noqa: BLE001
                print(f"  [seed {seed}] ERROR: {exc}", file=sys.stderr)
                continue
            mine_scores.append(m)
            opp_scores.append(o)
            if m > o:
                wins += 1
            elif m < o:
                losses += 1
            else:
                ties += 1

        if not mine_scores:
            summary[opp] = {"error": "no successful episodes"}
            continue

        summary[opp] = {
            "episodes": len(mine_scores),
            "record": f"{wins}W-{losses}L-{ties}T",
            "win_rate": round(wins / len(mine_scores), 3),
            "my_mean": round(statistics.mean(mine_scores), 1),
            "my_median": round(statistics.median(mine_scores), 1),
            "my_min": round(min(mine_scores), 1),
            "my_max": round(max(mine_scores), 1),
            "my_stdev": round(statistics.stdev(mine_scores), 1) if len(mine_scores) > 1 else 0.0,
            "opp_mean": round(statistics.mean(opp_scores), 1),
        }
        print(f"\nvs {opp:<8} {summary[opp]['record']:<12} "
              f"win_rate={summary[opp]['win_rate']:<6} "
              f"my_mean=${summary[opp]['my_mean']:<9} "
              f"opp_mean=${summary[opp]['opp_mean']}")

    with open("benchmark_results.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print("\nwrote benchmark_results.json")
    return summary


if __name__ == "__main__":
    main()
