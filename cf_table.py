"""检验「固定动作表」能否跨种子使用。

背景：棋盘布局、作物参数、初始资金都是常数；每局唯一的随机来源是
      杂草生成(0.5%/天)与商店解锁顺序。若某个高分 agent 的动作序列
      在不同种子下几乎相同，那它就是一张与地图无关的宏观时间表 ——
      这类表可以直接当提交用。

做法：把 (源 episode, 座位) 的动作表（按正确错位 t+1 取用）当作候选，
      放到**全部 12 局 × 2 座位**的真实反事实里跑，看它的份额。

用法：
  python cf_table.py --src 107983407 --seat 0
  python cf_table.py --src 108035195 --seat 1 --cand candidates/V38.py   # 对比
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
from cf_real import ACTION_SHIFT, PASS, load_replays, recorded_agent, replay_index  # noqa: E402


def table_agent(table, shift=ACTION_SHIFT):
    """把动作表包成 agent。表是 {step: action}。"""
    def fn(obs):
        e = table.get(obs.get("step", 0) + shift)
        if not isinstance(e, dict):
            return dict(PASS)
        return {"farmer": e.get("farmer", ["PASS"]),
                "hands": e.get("hands", []) or [],
                "market": e.get("market", []) or []}
    return fn


def build_table(replay, seat):
    out = {}
    for t, row in enumerate(replay["steps"]):
        if seat < len(row):
            a = row[seat].get("action")
            if isinstance(a, dict):
                out[t] = a
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays", default="_docx/sept_replays.pkl")
    ap.add_argument("--src", required=True, help="动作表来源 episode")
    ap.add_argument("--seat", type=int, required=True)
    ap.add_argument("--cand", default="", help="额外的对比候选（文件路径）")
    ap.add_argument("--exclude-src", action="store_true",
                    help="跳过源 episode 本身（只统计跨局表现）")
    ap.add_argument("--out", default="_docx/cf_table.txt")
    args = ap.parse_args()

    reps = load_replays(args.replays)
    items = sorted(reps.items(), key=lambda kv: kv[0])

    with open(args.replays, "rb") as fh:
        raw = pickle.load(fh)

    src_rep = json.loads(raw[args.src])
    src_table = build_table(src_rep, args.seat)
    cands = [("T", table_agent(src_table))]
    if args.cand:
        with open(args.cand, encoding="utf-8") as fh:
            cands.append((args.cand, get_last_callable(
                fh.read().lstrip("\ufeff"), path=args.cand)))

    L = []
    for name, cfn in cands:
        L.append(f"候选 = {name}" + (f"  ← 来自 episode {args.src} 座位 {args.seat}"
                                     if name == "T" else ""))
        L.append("  episode      对手        我座   我方资金    对手资金     结果     分差")
        win = lose = tie = 0
        mytot = optot = 0
        for eid, rep in items:
            if args.exclude_src and eid == args.src:
                continue
            idx = replay_index(rep)
            if idx["seed"] is None:
                continue
            for opp_seat in (0, 1):
                my_seat = 1 - opp_seat
                pair = [None, None]
                pair[my_seat] = cfn
                pair[opp_seat] = recorded_agent(idx["acts"], opp_seat)
                env = make("kaggriculture",
                           configuration={"episodeSteps": 720, "seed": idx["seed"]},
                           debug=False)
                env.run(pair)
                r = [float(s.reward or 0) for s in env.steps[-1]]
                mine, theirs = r[my_seat], r[opp_seat]
                mytot += mine
                optot += theirs
                if mine > theirs:
                    res = "胜"
                    win += 1
                elif mine < theirs:
                    res = "负"
                    lose += 1
                else:
                    res = "平"
                    tie += 1
                L.append(f"  {eid:<12} seat{opp_seat}    我座{my_seat} "
                         f"{mine:>10,.0f} {theirs:>10,.0f}   {res}  {mine - theirs:>+10,.0f}")
        n = win + lose + tie
        L.append("")
        L.append(f"  {win}胜 {lose}负 {tie}平   胜率 {win / n:.1%}   "
                 f"平均份额 {mytot / (mytot + optot):.1%}   "
                 f"均分 {mytot / n:,.0f} / {optot / n:,.0f}")
        L.append("")

    text = "\n".join(L)
    open(args.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
