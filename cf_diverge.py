"""定位重放发散点：逐日对比重放资金 vs 回放记录资金。"""
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
for t in range(0, 720):
    rec = rep["steps"][t]
    got = env.steps[t]
    if t % 24 != 23:
        continue
    day = t // 24
    # 记录：该步观测里的资金 (即该步开始时的资金)
    rb = [rec[i]["observation"]["farms"][i]["money"] for i in range(2)]
    # 重放：同理，但 env.steps[t] 是该步开始时的状态
    gb = []
    for i in range(2):
        o = got[i]["observation"]
        gb.append(o["farms"][i]["money"])
    out.append(f"day {day:>2}  记录 {rb[0]:>9,.0f}/{rb[1]:>9,.0f}   重放 {gb[0]:>9,.0f}/{gb[1]:>9,.0f}")

out.append("")
out.append("最终步记录 " + json.dumps([rep["steps"][-1][i]["observation"]["farms"][i]["money"] for i in range(2)]))
out.append("最终步重放 " + json.dumps([env.steps[-1][i].observation.farms[i]["money"] for i in range(2)]))
open("_docx/cf_diverge.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out[:12]))
print("...")
print("\n".join(out[-4:]))
