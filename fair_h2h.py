"""
公平对打：在**对手各自的原地图**上测 V38。

此前所有"V38 碾压回放 agent"的结论都有偏 ——
固定动作表只对各自地图最优，换种子会严重退化，等于让对手绑着一只手打。

本版从回放的 info.seed 取回原地图种子，在同一张图上对打。
这是 V38 真实强度（相对 2,809-2,908 分那一档）的检验。
"""
import contextlib
import glob
import io
import json
import os
import pickle
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


# 从 pickle 取每个 episode 的 seed 与 rating
reps = pickle.load(open("_docx/sept_replays.pkl", "rb"))
meta = {}
import csv
with open("_docx/sept_targets.csv", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        meta[row["episode_id"]] = row

info = {}
for eid, raw in reps.items():
    d = json.loads(raw) if isinstance(raw, str) else raw
    sd = (d.get("info") or {}).get("seed")
    rw = d.get("rewards") or [0, 0]
    t = meta.get(eid, {})
    seat = int(t.get("seat", 0))
    info[eid] = {"seed": sd, "rating": float(t.get("rating", 0)),
                 "seat": seat, "my_orig_bank": float(t.get("bank", 0)),
                 "opp_orig_bank": rw[1 - seat] if len(rw) > 1 else 0}

V38 = load("candidates/V38.py")
out = [f"公平对打：V38 在对手原地图上（{len(info)} 个 9 月高分 agent）", ""]
out.append(f"{'episode':>10} {'rating':>9} {'seed':>11} {'V38资金':>10} "
           f"{'对手资金':>10} {'对手原资金':>10} {'结果':>5}")
out.append("-" * 76)

w = l = 0
rows = []
for eid, d in sorted(info.items(), key=lambda kv: -kv[1]["rating"]):
    fn = f"opponents_src/sept/sept_{eid}_s{d['seat']}.py"
    if not os.path.exists(fn) or d["seed"] is None:
        out.append(f"{eid:>10} {'seed缺失或文件缺失':>40}")
        continue
    opp = load(fn)
    # V38 坐对手原本的对面座位，保持地图一致
    v_seat = 1 - d["seat"]
    first, second = (V38, opp) if v_seat == 0 else (opp, V38)
    env = make("kaggriculture",
               configuration={"episodeSteps": 720, "seed": int(d["seed"])}, debug=False)
    env.run([first, second])
    st = env.steps[-1]
    if st[0].status != "DONE" or st[1].status != "DONE":
        out.append(f"{eid:>10} 状态异常")
        continue
    m0, m1 = float(st[0].reward or 0), float(st[1].reward or 0)
    mv, mo = (m0, m1) if v_seat == 0 else (m1, m0)
    res = "V38胜" if mv > mo else ("对手胜" if mo > mv else "平")
    if mv > mo:
        w += 1
    elif mo > mv:
        l += 1
    rows.append((eid, d["rating"], mv, mo))
    out.append(f"{eid:>10} {d['rating']:>9,.1f} {int(d['seed']):>11} {mv:>10,.0f} "
               f"{mo:>10,.0f} {d['my_orig_bank']:>10,.0f} {res:>5}")

if rows:
    n = w + l
    out.append("")
    out.append(f"合计 V38 {w}W-{l}L   胜率 {w/n:.1%}" if n else "无有效对局")
    out.append(f"V38 平均资金 {statistics.mean(r[2] for r in rows):,.0f}   "
               f"对手平均 {statistics.mean(r[3] for r in rows):,.0f}")
    out.append("")
    out.append("对照：这些对手在原局中的资金（它们自己打出来的）：")
    out.append(f"  平均 {statistics.mean(r[3] for r in rows):,.0f}")

text = "\n".join(out)
with open("_docx/fair_h2h.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
