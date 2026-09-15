"""
聚合多局回放：算出我方的真实胜负记录与行为特征。

注意区分：Kaggle 的技能分是 Elo 式，排名靠对局胜负而非单局资金。
所以"单局资金"和"技能分"是两个不同量，要把胜负单独统计。

我方账号名可能显示为 "Yash Apps"（账号显示名）而非用户名，
所以两个都当作"我方"候选。
"""
import glob
import json
import os
import statistics
from collections import Counter

MY_NAMES = {"yash apps", "yashwanthgajji", "linjunren1016"}
MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}


def behaviour(steps, p):
    ops = Counter()
    for st in steps:
        act = st[p].get("action")
        if not act:
            continue
        f = act.get("farmer")
        if isinstance(f, list) and f:
            ops[f[0]] += 1
        for h in act.get("hands", []) or []:
            if isinstance(h, list) and h:
                ops[h[0]] += 1
    total = sum(ops.values())
    move = sum(v for k, v in ops.items() if k in MOVE)
    return ops, total, (move / total if total else 0)


rows = []
for path in sorted(glob.glob("replays/episode-*-replay.json")):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    info = d.get("info", {})
    agents = [a.get("Name") for a in info.get("Agents", [])]
    teams = info.get("TeamNames", []) or agents
    rewards = d.get("rewards", [])
    steps = d["steps"]

    me = None
    for p in (0, 1):
        nm = (agents[p] or "").lower()
        tm = (teams[p] or "").lower()
        if nm in MY_NAMES or tm in MY_NAMES:
            me = p
    if me is None:
        rows.append((os.path.basename(path), None, agents, rewards, None))
        continue
    opp = 1 - me
    my_money, op_money = rewards[me], rewards[opp]
    ops, total, mfrac = behaviour(steps, me)
    _, _, omfrac = behaviour(steps, opp)
    water = ops.get("WATER", 0) / total if total else 0
    rows.append({
        "file": os.path.basename(path),
        "me": me, "my_name": agents[me], "opp_name": agents[opp],
        "my_money": my_money, "op_money": op_money,
        "win": my_money > op_money,
        "total": total, "move_frac": mfrac, "water_frac": water,
        "opp_move_frac": omfrac,
    })

out = ["多局回放聚合", ""]
played = [r for r in rows if isinstance(r, dict)]
unknown = [r for r in rows if not isinstance(r, dict)]
out.append(f"识别出我方的对局: {len(played)} / {len(rows)}")
if unknown:
    out.append(f"未能识别我方: {[u[0] for u in unknown]}")
out.append("")

wins = sum(1 for r in played if r["win"])
out.append(f"胜负: {wins}胜 {len(played)-wins}负   胜率 {wins/len(played):.1%}")
out.append(f"平均我方资金 ${statistics.mean(r['my_money'] for r in played):,.0f}   "
           f"对手 ${statistics.mean(r['op_money'] for r in played):,.0f}")
out.append("")

out.append(f"{'我方资金':>10} {'对手资金':>10} {'结果':>4} {'我方移动':>8} {'我方浇水':>8} {'对手移动':>8}  对手")
for r in sorted(played, key=lambda x: -x["my_money"]):
    out.append(f"{r['my_money']:>10,.0f} {r['op_money']:>10,.0f} "
               f"{'胜' if r['win'] else '负':>4} "
               f"{r['move_frac']:>8.1%} {r['water_frac']:>8.1%} "
               f"{r['opp_move_frac']:>8.1%}  {r['opp_name']}")

out.append("")
out.append(f"我方移动占比 平均 {statistics.mean(r['move_frac'] for r in played):.1%}")
out.append(f"我方浇水占比 平均 {statistics.mean(r['water_frac'] for r in played):.1%}")
out.append(f"对手移动占比 平均 {statistics.mean(r['opp_move_frac'] for r in played):.1%}")

# 胜局 vs 负局的行为差异
w = [r for r in played if r["win"]]
l = [r for r in played if not r["win"]]
if w and l:
    out.append("")
    out.append("胜局 vs 负局（我方）：")
    out.append(f"  胜局 移动 {statistics.mean(r['move_frac'] for r in w):.1%}  "
               f"浇水 {statistics.mean(r['water_frac'] for r in w):.1%}  "
               f"资金 {statistics.mean(r['my_money'] for r in w):,.0f}")
    out.append(f"  负局 移动 {statistics.mean(r['move_frac'] for r in l):.1%}  "
               f"浇水 {statistics.mean(r['water_frac'] for r in l):.1%}  "
               f"资金 {statistics.mean(r['my_money'] for r in l):,.0f}")

with open("_docx/aggregate.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
