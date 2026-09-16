"""找出重放与录像第一个不一致的回合，并打印该回合双方动作与关键状态。"""
import contextlib
import io
import json
import pickle
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")
from cf_real import recorded_agent, replay_index  # noqa: E402

eid = sys.argv[1] if len(sys.argv) > 1 else "107983407"
d = pickle.load(open("_docx/sept_replays.pkl", "rb"))
rep = json.loads(d[eid])
idx = replay_index(rep)

env = make("kaggriculture",
           configuration={"episodeSteps": 720, "seed": idx["seed"]}, debug=False)
env.run([recorded_agent(idx["acts"], 0), recorded_agent(idx["acts"], 1)])

out = []


def snap_step(step_no, recorded):
    """返回该回合开始时的可比状态。"""
    s = []
    for i in range(2):
        if recorded:
            o = rep["steps"][step_no][i]["observation"]
        else:
            o = env.steps[step_no][i].observation
        farms = o["farms"]
        pf = farms[i]
        s.append({
            "money": pf["money"],
            "hires": pf.get("hires_today"),
            "hands": len(pf.get("hands", [])),
            "farmer": tuple(pf["farmer"]),
            "shed": {k: v for k, v in (o["private"]["shed"] or {}).items() if v},
            "seeds": {k: v for k, v in (o["private"]["seeds"] or {}).items() if v},
            "mkt": {k: v for k, v in (o["market"]["inventory"] or {}).items() if v},
            "prices": o["market"]["prices"],
            "town": list(o["town"]["unlocked_shops"]),
            "tiles": [[json.dumps(t, sort_keys=True) if isinstance(t, dict) else t
                       for t in row] for row in pf["tiles"]],
        })
    return s


first = None
for t in range(720):
    a = snap_step(t, True)
    b = snap_step(t, False)
    if a != b:
        first = t
        break

out.append(f"episode {eid}  seed={idx['seed']}")
out.append(f"第一个不一致回合: step={first}  day={first // 24}  hour={first % 24}")
out.append("")

if first is not None:
    a = snap_step(first, True)
    b = snap_step(first, False)
    for i in range(2):
        out.append(f"--- 玩家 {i} ---")
        for k in a[i]:
            if a[i][k] != b[i][k]:
                out.append(f"  {k}:")
                out.append(f"     录像 {json.dumps(a[i][k], ensure_ascii=False, default=str)[:600]}")
                out.append(f"     重放 {json.dumps(b[i][k], ensure_ascii=False, default=str)[:600]}")
    out.append("")
    out.append("该回合录像动作:")
    for i in range(2):
        act = rep["steps"][first][i]["action"]
        out.append(f"  玩家{i}: {json.dumps(act, ensure_ascii=False)[:800]}")
    out.append("")
    out.append("上一回合(step-1)录像动作:")
    for i in range(2):
        act = rep["steps"][first - 1][i]["action"]
        out.append(f"  玩家{i}: {json.dumps(act, ensure_ascii=False)[:800]}")

text = "\n".join(out)
open("_docx/cf_firstdiff.txt", "w", encoding="utf-8").write(text)
print(text[:4000])
