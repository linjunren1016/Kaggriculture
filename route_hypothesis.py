"""检验高分 agent 是不是「按商店解锁模式选路线」的静态表。

取同一名选手在 11 局里的动作表，按前 3 个解锁商店的模式分组，
比较「同模式内」与「跨模式」的动作一致率。
若同模式内明显更一致，说明它是路线选择器，可以照抄成路线库。
"""
import collections
import json
import pickle

raw = pickle.load(open("_docx/sept_replays.pkl", "rb"))

target = "ADARSH DWIVEDI"
recs = []
for eid, js in raw.items():
    rep = json.loads(js)
    names = [a["Name"] for a in rep["info"]["Agents"]]
    if target not in names:
        continue
    seat = names.index(target)
    shops = None
    for t in range(720):
        s = rep["steps"][t][seat]["observation"]["town"]["unlocked_shops"]
        if len(s) >= 3:
            shops = tuple(s[:3])
            break
    tab = {}
    for i, row in enumerate(rep["steps"]):
        a = row[seat].get("action")
        if isinstance(a, dict):
            tab[i] = json.dumps(a, sort_keys=True)
    recs.append((eid, shops, tab))

recs.sort(key=lambda r: str(r[1]))
L = []
L.append(f"{target}  共 {len(recs)} 局")
L.append("")
L.append(" episode      前3个解锁商店")
for eid, shops, _ in recs:
    L.append(f" {eid:<12} {shops}")

groups = collections.defaultdict(list)
for eid, shops, tab in recs:
    groups[str(shops)].append(eid)

L.append("")
L.append("按模式分组的表内一致率")
for key, ids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    if len(ids) < 2:
        L.append(f" {key}  只有 {len(ids)} 局")
        continue
    tabs = {eid: t for eid, s, t in recs if eid in ids}
    pair = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = tabs[ids[i]], tabs[ids[j]]
            common = set(a) & set(b)
            same = sum(1 for k in common if a[k] == b[k])
            pair.append(same / len(common))
    L.append(f" {key}  {len(ids)} 局  组内两两一致率均值 {sum(pair)/len(pair):.1%}")

L.append("")
L.append("跨模式一致率")
keys = sorted(groups)
cross = []
for i in range(len(keys)):
    for j in range(i + 1, len(keys)):
        for a_id in groups[keys[i]]:
            for b_id in groups[keys[j]]:
                a = dict(recs)[a_id][2] if False else None
        ta = {eid: t for eid, s, t in recs if eid in groups[keys[i]]}
        tb = {eid: t for eid, s, t in recs if eid in groups[keys[j]]}
        for x in ta:
            for y in tb:
                a, b = ta[x], tb[y]
                common = set(a) & set(b)
                same = sum(1 for k in common if a[k] == b[k])
                cross.append(same / len(common))
if cross:
    L.append(f" 跨模式两两一致率均值 {sum(cross)/len(cross):.1%}  （{len(cross)} 对）")
else:
    L.append(" 只有一个模式，无法比较")

text = "\n".join(L)
open("_docx/route_hypothesis.txt", "w", encoding="utf-8").write(text)
print(text)
