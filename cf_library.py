"""路线库候选：把同一名高分选手在多局里的动作表按「商店前缀」索引起来，
新对局按观测到的商店解锁前缀就近选取对应路线。

动机
----
实测：ADARSH 的 11 局动作表两两一致率在 25%~96% 之间摆动，且按 5 类粗分类
分组后，组内还能分成 ~90% 与 ~60% 两簇 —— 说明它是「按商店（镇需求）选
路线」的静态表，而不是逐局重新规划。既然如此，只要手里有足够多局它的表，
就能在运行时按商店前缀挑到对应的那张，复现它的实力。

评测（留一法）
----
对第 i 局评估时，路线库里**剔除**第 i 局自己的表，只用其余局建库，
避免把测试局本身的信息泄漏进来。

用法
----
python cf_library.py --agent "ADARSH DWIVEDI" --out _docx/cf_library.txt
"""
import argparse
import contextlib
import io
import json
import os
import pickle
import sys
import tempfile

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")
from cf_real import ACTION_SHIFT, PASS, recorded_agent, replay_index  # noqa: E402

TEMPLATE = '''"""路线库：{agent} 的 {n} 局录像动作表 + 按商店前缀选取。
基础执行层来自 V38(main.py) 的修复/护栏。自动生成，勿手改。
"""
{base}

_LIB = {lib}


def _prefix_score(entry, shops, k):
    pref = entry["prefix"]
    score = 0
    for i in range(k):
        if i < len(pref) and pref[i] == shops[i]:
            score += 1
        else:
            score -= 1
    return score


def _kawa_actions(obs):
    town = None
    if isinstance(obs, dict):
        town = obs.get("town")
    else:
        town = getattr(obs, "town", None)
    shops = list((town or {{}}).get("unlocked_shops", []) or []) if hasattr(town, "get") \\
        else list(getattr(town, "unlocked_shops", []) or [])
    k = min(len(shops), 3)
    best, best_score = _LIB[0]["table"], None
    for entry in _LIB:
        score = _prefix_score(entry, shops, k)
        if best_score is None or score > best_score:
            best, best_score = entry["table"], score
    return best


def _library_entry(obs):
    """最后绑定的可调用对象 = 实际入口。"""
    return agent(obs)
'''


def build_library(raw, agent, exclude=None):
    lib = []
    for eid, js in sorted(raw.items()):
        if exclude is not None and eid == exclude:
            continue
        rep = json.loads(js)
        names = [a["Name"] for a in rep["info"]["Agents"]]
        if agent not in names:
            continue
        seat = names.index(agent)
        prefix = []
        for t in range(720):
            s = list(rep["steps"][t][seat]["observation"]["town"]["unlocked_shops"])
            if len(s) > len(prefix):
                prefix = s
        table = []
        for t in range(len(rep["steps"]) - 1):
            j = t + ACTION_SHIFT
            a = rep["steps"][j][seat].get("action") if j < len(rep["steps"]) else None
            if not isinstance(a, dict):
                a = PASS
            table.append({
                "farmer": list(a.get("farmer") or ["PASS"]),
                "hands": [list(h or ["PASS"]) for h in (a.get("hands") or [])],
                "market": [list(m) for m in (a.get("market") or [])],
            })
        lib.append({"eid": eid, "prefix": prefix[:5], "table": table})
    return lib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays", default="_docx/sept_replays.pkl")
    ap.add_argument("--agent", default="ADARSH DWIVEDI")
    ap.add_argument("--base", default="main.py")
    ap.add_argument("--out", default="_docx/cf_library.txt")
    ap.add_argument("--keep-tmp", action="store_true")
    args = ap.parse_args()

    with open(args.replays, "rb") as fh:
        raw = pickle.load(fh)
    with open(args.base, encoding="utf-8") as fh:
        base_src = fh.read().lstrip("\ufeff")

    items = []
    for eid, js in sorted(raw.items()):
        rep = json.loads(js)
        idx = replay_index(rep)
        if idx["seed"] is not None:
            items.append((eid, rep, idx))

    L = [f"路线库 = {args.agent} 的录像动作表（留一法）", ""]
    L.append(" episode      对手            我座   我方资金    对手资金     结果     分差   库内条数")
    win = lose = 0
    mytot = optot = 0
    tmpdir = tempfile.mkdtemp(prefix="cf_lib_")
    for eid, rep, idx in items:
        lib = build_library(raw, args.agent, exclude=eid)
        if not lib:
            L.append(f" {eid}  库为空，跳过")
            continue
        src = TEMPLATE.format(agent=args.agent, n=len(lib), base=base_src,
                              lib=repr(lib))
        path = os.path.join(tmpdir, f"lib_{eid}.py")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src)
        cfn = get_last_callable(src, path=path)
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
            else:
                res = "负"
                lose += 1
            L.append(f" {eid:<12} seat{opp_seat}({idx['names'][opp_seat][:11]:<11}) "
                     f"我座{my_seat} {mine:>10,.0f} {theirs:>10,.0f}   {res}  "
                     f"{mine - theirs:>+10,.0f}   {len(lib)}")
    n = win + lose
    L.append("")
    if n:
        L.append(f" 留一法结果：{win}胜 {lose}负   胜率 {win / n:.1%}   "
                 f"平均份额 {mytot / (mytot + optot):.1%}   "
                 f"均分 {mytot / n:,.0f} / {optot / n:,.0f}")
    if not args.keep_tmp:
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)
    text = "\n".join(L)
    open(args.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
