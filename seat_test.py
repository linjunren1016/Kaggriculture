"""
Seat (先后手) asymmetry test.

Why this matters: the final leaderboard is a Bradley-Terry tournament, so every
agent plays both seat 0 and seat 1. The official evaluation page also notes that
matches are paired against similar skill ratings. If a policy is systematically
stronger in one seat, that is a real, fixable win-rate leak that no amount of
tuning elsewhere will recover.

Two modes:
  1. self-play  : agent vs a copy of itself, both seats -> pure seat effect
  2. vs opponent: agent in seat 0 and seat 1 against a fixed opponent

Usage:
    python seat_test.py --episodes 8
    python seat_test.py --episodes 8 --opponent starter
"""
import argparse
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def play(agent, opponent, seed, steps=720):
    """Return (agent_money, opponent_money, agent_status)."""
    env = make("kaggriculture",
               configuration={"episodeSteps": steps, "seed": seed}, debug=True)
    env.run([agent, opponent])
    final = env.steps[-1]
    return (float(final[0].reward or 0.0),
            float(final[1].reward or 0.0),
            final[0].status)


def summarize(label, results):
    wins = sum(1 for m, o in results if m > o)
    losses = sum(1 for m, o in results if m < o)
    ties = sum(1 for m, o in results if m == o)
    margins = [m - o for m, o in results]
    n = len(results)
    print(f"  {label:<22} {wins}W-{losses}L-{ties}T  "
          f"win_rate={wins/n:.3f}  "
          f"mean_margin={statistics.mean(margins):+9.0f}  "
          f"my_money={statistics.mean(m for m, _ in results):9.0f}")
    return {"wins": wins, "losses": losses, "ties": ties, "n": n,
            "win_rate": wins / n,
            "mean_margin": statistics.mean(margins),
            "my_money": statistics.mean(m for m, _ in results)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="main.py")
    ap.add_argument("--opponent", default=None,
                    help="omit for self-play seat test")
    ap.add_argument("--episodes", type=int, default=8)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    opp = args.opponent if args.opponent else args.agent
    label = f"vs {args.opponent}" if args.opponent else "self-play"

    print(f"seat test: {args.agent}  {label}  "
          f"({args.episodes} seeds x 2 seats)\n")

    # Seat 0: agent listed first. Seat 1: agent listed second.
    seat0, seat1 = [], []
    for i in range(args.episodes):
        seed = 2000 + i
        m, o, status = play(args.agent, opp, seed, args.steps)
        if status != "DONE":
            print(f"  [seed {seed} seat0] status={status} (skipped)")
        else:
            seat0.append((m, o))

        m, o, status = play(opp, args.agent, seed, args.steps)
        if status != "DONE":
            print(f"  [seed {seed} seat1] status={status} (skipped)")
        else:
            # In this call the agent is player 1, so swap to keep "mine" first.
            seat1.append((o, m))

    if not seat0 or not seat1:
        print("no successful episodes")
        return 1

    r0 = summarize("agent in seat 0", seat0)
    r1 = summarize("agent in seat 1", seat1)
    overall = seat0 + seat1
    summarize("overall (both seats)", overall)

    gap = r0["win_rate"] - r1["win_rate"]
    print(f"\n  seat0 - seat1 win-rate gap: {gap:+.3f}")
    if abs(gap) >= 0.15:
        print("  => MATERIAL SEAT ASYMMETRY. Worth investigating a seat-specific policy.")
    else:
        print("  => No material seat asymmetry at this sample size.")
    print(f"\n  NOTE: only {len(overall)} episodes; treat as a smoke signal, not proof.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
