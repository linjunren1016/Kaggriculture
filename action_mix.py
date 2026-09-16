"""对比「候选 agent」与「录像里的高分 agent」的单位动作构成。

回答的问题：同样的回合数，对手把单位回合花在哪，我们花在哪，差在哪。
"""
import argparse
import collections
import contextlib
import io
import json
import pickle
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")
from cf_real import recorded_agent, replay_index  # noqa: E402

MOVE = {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}


def mix(steps, seat, ndays=30):
    c = collections.Counter()
    for t in range(min(ndays * 24, len(steps))):
        entry = steps[t][seat]
        a = entry.get("action") if isinstance(entry, dict) else None
        if not isinstance(a, dict):
            continue
        units = [a.get("farmer")] + list(a.get("hands") or [])
        for u in units:
            if isinstance(u, str):
                u = [u]
            if not isinstance(u, list) or not u:
                continue
            c[u[0]] += 1
    return c


def show(c, total_label=""):
    tot = sum(c.values())
    return [f"  {k:<20}{c[k]:>8,}  {c[k] / tot:>6.1%}" for k in
            sorted(c, key=lambda k: -c[k])], tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", default="108035195")
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--cand", default="candidates/V38.py")
    ap.add_argument("--out", default="_docx/action_mix.txt")
    args = ap.parse_args()

    raw = pickle.load(open("_docx/sept_replays.pkl", "rb"))
    rep = json.loads(raw[args.episode])
    idx = replay_index(rep)
    opp_seat = 1 - args.seat

    with open(args.cand, encoding="utf-8") as fh:
        cand = get_last_callable(fh.read().lstrip("\ufeff"), path=args.cand)

    pair = [None, None]
    pair[args.seat] = cand
    pair[opp_seat] = recorded_agent(idx["acts"], opp_seat)
    env = make("kaggriculture",
               configuration={"episodeSteps": 720, "seed": idx["seed"]}, debug=False)
    env.run(pair)

    me_live = mix(env.steps, args.seat)
    op_live = mix(env.steps, opp_seat)
    me_orig = mix(rep["steps"], args.seat)
    op_orig = mix(rep["steps"], opp_seat)

    L = [f"episode {args.episode}  seed={idx['seed']}",
         f"候选 {args.cand} 座位 {args.seat}（录像里 {idx['names'][args.seat]}）",
         ""]
    for title, c in ((f"我(候选) 本局", me_live),
                     (f"录像里同座 {idx['names'][args.seat]}", me_orig),
                     (f"对手 {idx['names'][opp_seat]} 本局", op_live),
                     (f"录像里对手 {idx['names'][opp_seat]}", op_orig)):
        rows, tot = show(c)
        L.append(f"── {title}   单位动作总计 {tot:,}")
        L.extend(rows)
        L.append("")

    # 关键比率
    def g(c, *keys):
        return sum(c[k] for k in keys)

    L.append("关键对比")
    L.append(f"  {'':<16}{'候选':>10}{'录像同座':>10}{'对手本局':>10}{'录像对手':>10}")
    for label, keys in (("移动+空过", tuple(MOVE)),
                        ("PLANT", ("PLANT",)),
                        ("HARVEST", ("HARVEST",)),
                        ("WATER", ("WATER",)),
                        ("FEED+CARE", ("FEED", "CARE")),
                        ("PICKUP+PLACE", ("PICKUP", "PLACE", "DROP")),
                        ("COLLECT_FERT", ("COLLECT_FERTILIZER",)),
                        ("FERTILIZE", ("FERTILIZE",)),
                        ("DIG", ("DIG",)),
                        ("BUILD", ("BUILD_COOP", "BUILD_PASTURE"))):
        L.append(f"  {label:<16}{g(me_live,*keys):>10,}{g(me_orig,*keys):>10,}"
                 f"{g(op_live,*keys):>10,}{g(op_orig,*keys):>10,}")

    text = "\n".join(L)
    open(args.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
