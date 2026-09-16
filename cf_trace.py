"""反事实逐日追踪：把候选 agent 放进真实回放，逐日对比双方产出与市场行为。

用法:
  python cf_trace.py --episode 107983407 --cand candidates/V38.py --seat 0
"""
import argparse
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

OPS_FARM = ("PLANT", "HARVEST", "WATER", "FEED", "CARE", "BUILD_PASTURE",
            "BUILD_COOP", "PLACE", "COLLECT_FERTILIZER", "DIG")


def tally(steps, seat, ndays=30):
    """统计某座位每天的：资金、种植/收获次数、卖出数量、买入种子数、雇工数。"""
    rows = []
    for d in range(ndays):
        lo, hi = d * 24, d * 24 + 24
        planted = harvested = sold = bought_seed = hires = 0
        planted_crops = {}
        for t in range(lo, min(hi, len(steps))):
            entry = steps[t][seat]
            act = entry.get("action") if isinstance(entry, dict) else None
            if not isinstance(act, dict):
                continue
            units = [act.get("farmer")] + list(act.get("hands") or [])
            for u in units:
                if isinstance(u, list) and u:
                    if u[0] == "PLANT" and len(u) > 1:
                        planted += 1
                        planted_crops[u[1]] = planted_crops.get(u[1], 0) + 1
                    elif u[0] == "HARVEST":
                        harvested += 1
            for m in act.get("market") or []:
                if not isinstance(m, list) or not m:
                    continue
                if m[0] == "SELL":
                    sold += m[2] if len(m) > 2 else 0
                elif m[0] == "BUY_SEED":
                    bought_seed += m[2] if len(m) > 2 else 0
                elif m[0] == "HIRE":
                    hires += 1
        # 日终资金：该天最后一个回合的观测
        t = min(hi - 1, len(steps) - 1)
        obs = steps[t][seat].get("observation", {})
        farms = obs.get("farms", [])
        money = farms[seat]["money"] if seat < len(farms) else None
        rows.append({
            "day": d, "money": money, "planted": planted, "harvested": harvested,
            "sold": sold, "bought_seed": bought_seed, "hires": hires,
            "crops": planted_crops,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--replays", default="_docx/sept_replays.pkl")
    ap.add_argument("--cand", required=True)
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--out", default="_docx/cf_trace.txt")
    args = ap.parse_args()

    with open(args.replays, "rb") as fh:
        raw = pickle.load(fh)
    rep = json.loads(raw[args.episode])
    idx = replay_index(rep)

    with open(args.cand, encoding="utf-8") as fh:
        cfn = get_last_callable(fh.read().lstrip("\ufeff"), path=args.cand)

    opp_seat = 1 - args.seat
    pair = [None, None]
    pair[args.seat] = cfn
    pair[opp_seat] = recorded_agent(idx["acts"], opp_seat)
    env = make("kaggriculture",
               configuration={"episodeSteps": 720, "seed": idx["seed"]}, debug=False)
    env.run(pair)

    mine = tally(env.steps, args.seat)
    theirs = tally(env.steps, opp_seat)
    orig_me = tally(rep["steps"], args.seat)   # 录像里原主在该座位的表现
    orig_op = tally(rep["steps"], opp_seat)

    L = []
    L.append(f"episode {args.episode}  seed={idx['seed']}")
    L.append(f"候选 {args.cand} 占座位 {args.seat}（录像里是 {idx['names'][args.seat]}）")
    L.append(f"对手座位 {opp_seat} 用录像动作（{idx['names'][opp_seat]}）")
    L.append("")
    L.append("        ── 本次反事实 ──        ── 录像原局 ──")
    L.append(" day   我资金   对手资金   我种植  我收获 | 我资金   对手资金   我种植")
    for a, b, c, d in zip(mine, theirs, orig_me, orig_op):
        L.append(f" {a['day']:>2}  {a['money']:>9,.0f} {b['money']:>9,.0f}"
                 f"   {a['planted']:>6} {a['harvested']:>7} |"
                 f" {c['money']:>9,.0f} {d['money']:>9,.0f}   {c['planted']:>6}")
    L.append("")

    def tot(rows, key):
        return sum(r[key] for r in rows)

    L.append("汇总")
    L.append(f"  {'':<10}{'本局(我)':>12}{'本局(对手)':>12}{'录像(我)':>12}{'录像(对手)':>12}")
    for key in ("planted", "harvested", "sold"):
        L.append(f"  {key:<10}{tot(mine,key):>12,.0f}{tot(theirs,key):>12,.0f}"
                 f"{tot(orig_me,key):>12,.0f}{tot(orig_op,key):>12,.0f}")
    L.append(f"  {'end money':<10}{mine[-1]['money']:>12,.0f}{theirs[-1]['money']:>12,.0f}"
             f"{orig_me[-1]['money']:>12,.0f}{orig_op[-1]['money']:>12,.0f}")

    crops_me, crops_op = {}, {}
    for r in mine:
        for k, v in r["crops"].items():
            crops_me[k] = crops_me.get(k, 0) + v
    for r in theirs:
        for k, v in r["crops"].items():
            crops_op[k] = crops_op.get(k, 0) + v
    L.append("")
    L.append(f"  我种植构成   {json.dumps(crops_me, sort_keys=True)}")
    L.append(f"  对手种植构成 {json.dumps(crops_op, sort_keys=True)}")

    text = "\n".join(L)
    open(args.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
