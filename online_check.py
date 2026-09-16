"""用我们自己线上提交的真实回放校验反事实装置。

做法：
  1. 读我们线上对局的回放；
  2. 用「把录像观测喂给候选，看输出是否等于录像动作」判定候选坐哪个座位；
  3. 把候选放回原座位、对手座位喂回录像动作，重跑整局；
  4. 若候选确定性，结果应与线上真实结果逐位一致 —— 这是对装置的终极校验。

用法：
  python online_check.py --dir replays_online --cand candidates/V38.py
"""
import argparse
import contextlib
import glob
import io
import json
import os
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")
from cf_real import recorded_agent, replay_index  # noqa: E402


def norm(a):
    if not isinstance(a, dict):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return {"farmer": a.get("farmer", ["PASS"]),
            "hands": a.get("hands", []) or [],
            "market": a.get("market", []) or []}


def seat_match(replay, cand):
    """候选在每个座位上的动作匹配率。"""
    steps = replay["steps"]
    out = []
    for seat in (0, 1):
        same = tot = 0
        for t in range(len(steps) - 1):
            obs = steps[t][seat].get("observation")
            if not isinstance(obs, dict):
                continue
            try:
                got = norm(cand(obs))
            except Exception:
                continue
            want = norm(steps[t + 1][seat].get("action"))
            tot += 1
            if got == want:
                same += 1
        out.append(same / tot if tot else 0.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="replays_online")
    ap.add_argument("--cand", default="candidates/V38.py")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="_docx/online_check.txt")
    args = ap.parse_args()

    with open(args.cand, encoding="utf-8") as fh:
        cand = get_last_callable(fh.read().lstrip("\ufeff"), path=args.cand)

    files = sorted(glob.glob(os.path.join(args.dir, "*.json")))
    if args.limit:
        files = files[:args.limit]

    L = [f"候选 {args.cand}   回放目录 {args.dir}（{len(files)} 局）", ""]
    L.append(" episode      我方座位  匹配率       线上资金      重跑资金     线上结果  重跑结果")
    agree = 0
    n = 0
    for fp in files:
        rep = json.load(open(fp, encoding="utf-8"))
        eid = rep["info"].get("EpisodeId")
        idx = replay_index(rep)
        if idx["seed"] is None:
            L.append(f" {eid}  无 seed，跳过")
            continue
        m = seat_match(rep, cand)
        my_seat = 0 if m[0] >= m[1] else 1
        opp = 1 - my_seat
        banks = idx["banks"]
        actual_win = banks[my_seat] > banks[opp]
        pair = [None, None]
        pair[my_seat] = cand
        pair[opp] = recorded_agent(idx["acts"], opp)
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": idx["seed"]}, debug=False)
        env.run(pair)
        got = [float(s.reward or 0) for s in env.steps[-1]]
        rerun_win = got[my_seat] > got[opp]
        same = abs(got[my_seat] - banks[my_seat]) < 1e-6 and \
            abs(got[opp] - banks[opp]) < 1e-6
        agree += same
        n += 1
        L.append(f" {eid:<12} {my_seat}     {m[0]:.0%}/{m[1]:.0%}   "
                 f"{banks[my_seat]:>10,.0f}/{banks[opp]:>10,.0f}  "
                 f"{got[my_seat]:>10,.0f}/{got[opp]:>10,.0f}   "
                 f"{'胜' if actual_win else '负'}       "
                 f"{'胜' if rerun_win else '负'}   "
                 f"{'逐位一致' if same else '不一致'}")
    L.append("")
    L.append(f"逐位复现 {agree}/{n}")
    text = "\n".join(L)
    open(args.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
