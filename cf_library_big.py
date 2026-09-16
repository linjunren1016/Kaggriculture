"""大规模路线库：从同一 submission 的大量真实回放里聚类出「路线」，
运行时按商店前缀选路线，执行层沿用 V38 的修复护栏。

为什么可行
----------
实测 ADARSH 的 11 局表两两一致率 25%~96%，按商店前缀能分出路线簇 ——
这类选手是「按镇需求选宏观时间表」的静态 agent。只要手握它足够多局的表，
就能把它复现成一个可跨局使用的库。

保真度指标
----------
对每一局，把库 agent 放回**原 agent 的座位**、对手座位喂回录像动作，
得到库 agent 的资金；与「原 agent 自己的表放回原座位」得到的资金
（= 该局真实资金）对比，即为库对该 agent 的保真度。

用法
----
python cf_library_big.py --dir replays_55341437 --sub 55341437 --limit 40
"""
import argparse
import base64
import contextlib
import glob
import io
import json
import os
import sys
import zlib

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")
from cf_real import ACTION_SHIFT, PASS, recorded_agent, replay_index  # noqa: E402

TEMPLATE = '''"""路线库成员：submission {sub} 的 {n} 条路线（来自公开回放）。
执行层沿用 V38(main.py) 的修复护栏。自动生成，勿手改。"""
{base}

_LIB = json.loads(zlib.decompress(base64.b85decode({blob})))


def _kawa_actions(obs):
    town = obs.get("town") if hasattr(obs, "get") else getattr(obs, "town", None)
    shops = list((town or {{}}).get("unlocked_shops", []) or []) if hasattr(town, "get") \\
        else list(getattr(town, "unlocked_shops", []) or [])
    k = min(len(shops), 3)
    best, best_score = _LIB[0]["t"], None
    for entry in _LIB:
        pref = entry["p"]
        score = 0
        for i in range(k):
            score += 1 if (i < len(pref) and pref[i] == shops[i]) else -1
        if best_score is None or score > best_score:
            best, best_score = entry["t"], score
    return best


def _library_entry(obs):
    return agent(obs)
'''


def norm(a):
    if not isinstance(a, dict):
        return dict(PASS)
    return {
        "farmer": list(a.get("farmer") or ["PASS"]),
        "hands": [list(h or ["PASS"]) for h in (a.get("hands") or [])],
        "market": [list(m) for m in (a.get("market") or [])],
    }


def build_table(rep, seat):
    steps = rep["steps"]
    out = []
    for t in range(len(steps) - 1):
        j = t + ACTION_SHIFT
        out.append(norm(steps[j][seat].get("action") if j < len(steps) else None))
    while len(out) < 720:
        out.append(dict(PASS))
    return out


def prefix_of(rep, seat):
    pref = []
    for t in range(720):
        s = list(rep["steps"][t][seat]["observation"]["town"]["unlocked_shops"])
        if len(s) > len(pref):
            pref = s
    return pref[:5]


def similarity(a, b):
    same = 0
    for x, y in zip(a, b):
        if x == y:
            same += 1
    return same / max(1, len(a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="replays_55341437")
    ap.add_argument("--sub", default="55341437")
    ap.add_argument("--seats")
    ap.add_argument("--base", default="main.py")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--out", default="_docx/cf_library_big.txt")
    args = ap.parse_args()

    seats = {}
    if args.seats and os.path.exists(args.seats):
        for line in open(args.seats, encoding="utf-8"):
            parts = line.strip().split(",")
            if len(parts) >= 2:
                seats[parts[0]] = int(parts[1])

    with open(args.base, encoding="utf-8") as fh:
        base_src = fh.read().lstrip("\ufeff")

    recs = []
    for fp in sorted(glob.glob(os.path.join(args.dir, "*.json"))):
        rep = json.load(open(fp, encoding="utf-8"))
        eid = str(rep["info"].get("EpisodeId"))
        if idx_seed(rep) is None:
            continue
        seat = seats.get(eid)
        if seat is None:
            continue
        recs.append((eid, seat, rep))
    if args.limit:
        recs = recs[:args.limit]
    L = [f"submission {args.sub}：{len(recs)} 局可评估", ""]

    # ---- 只聚类一次（对 343 局逐局重建库太慢）
    entries = [(eid, seat, prefix_of(rep, seat), build_table(rep, seat))
               for eid, seat, rep in recs]
    clusters = []
    for eid, seat, pref, tab in entries:
        for c in clusters:
            if similarity(c["tab"], tab) >= args.threshold:
                c["members"].append(eid)
                break
        else:
            clusters.append({"p": pref, "t": tab, "members": [eid]})
    L.append(f"聚类：{len(entries)} 张表 → {len(clusters)} 条路线"
             f"（阈值 {args.threshold}）")
    L.append(" 路线规模分布 " + str(sorted((len(c["members"]) for c in clusters),
                                          reverse=True)[:20]))
    L.append("")

    for eid, seat, rep in recs:
        opp = 1 - seat
        idx = replay_index(rep)
        # 留一法：每条路线挑一个「不是本局」的成员当代表
        lib = []
        for c in clusters:
            alt = next((m for m in c["members"] if m != eid), None)
            if alt is None:
                continue
            lib.append({"p": c["p"], "t": c["t"]})
        if not lib:
            L.append(f" {eid}  库为空，跳过")
            continue
        blob = base64.b85encode(zlib.compress(json.dumps(lib).encode(), 9)).decode()
        src = TEMPLATE.format(sub=args.sub, n=len(lib), base=base_src, blob=repr(blob))

        path = os.path.join("_docx", f"_lib_{eid}.py")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src)
        cfn = get_last_callable(src, path=path)

        pair = [None, None]
        pair[seat] = cfn
        pair[opp] = recorded_agent(idx["acts"], opp)
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": idx["seed"]}, debug=False)
        env.run(pair)
        got = [float(s.reward or 0) for s in env.steps[-1]]
        orig = idx["banks"][seat]
        L.append(f" {eid}  座位{seat}  库{len(lib)}条  "
                 f"库agent {got[seat]:>9,.0f}   原agent {orig:>9,.0f}   "
                 f"保真 {got[seat] / orig:>6.1%}   对手 {got[opp]:>9,.0f}")
        os.remove(path)
        open(args.out, "w", encoding="utf-8").write("\n".join(L))

    text = "\n".join(L)
    open(args.out, "w", encoding="utf-8").write(text)
    print(text)


def idx_seed(rep):
    return rep.get("info", {}).get("seed")


if __name__ == "__main__":
    main()
