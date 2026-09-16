"""把录像里高分 agent 的动作表装进 V38 的「修复层」，生成候选提交。

原理
----
V38(main.py) 本身就是一个静态动作表（_kawa_actions 返回 5 张按商店解锁
模式选定的 720 步表），外面套了一层修复/护栏：
    除草修复、喂食护栏、腾位、卖单排序、终局清算、手下列队对齐……
这层修复能让「表」在偏离本局地图时自动纠偏。

因此：把 _kawa_actions 换成**录像里高分 agent 的真实动作表**（按正确
错位 t+1 取用），其余修复层原样保留，就得到「强宏观计划 + 强纠偏」。

用法
----
python build_table_candidate.py --src 108075223 --seat 1 --out candidates/T_adarsh.py
python build_table_candidate.py --src 108075223 --seat 1 --no-repair --out candidates/T_adarsh_bare.py
"""
import argparse
import json
import pickle
import sys

sys.path.insert(0, ".")
from cf_real import ACTION_SHIFT  # noqa: E402

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def norm(a):
    if not isinstance(a, dict):
        return dict(PASS)
    return {
        "farmer": list(a.get("farmer") or ["PASS"]),
        "hands": [list(h or ["PASS"]) for h in (a.get("hands") or [])],
        "market": [list(m) for m in (a.get("market") or [])],
    }


OVERRIDE = '''

# ======================================================================
# 评测用改装：把基础计划换成录像里高分 agent 的真实动作表
# 来源 episode {eid} 座位 {seat}（{name}）
# 表已按正确错位烘入：_TABLE_OVERRIDE[t] 即第 t 回合要执行的动作
# ======================================================================
_TABLE_OVERRIDE = {table}


def _kawa_actions(obs):
    """重绑基础计划来源；名字已存在，不会改变它在模块字典里的位置。"""
    return _TABLE_OVERRIDE


def _table_entry(obs):
    """新的、最后绑定的可调用对象 —— 引擎按「最后新增的可调用对象」取入口。"""
    return agent(obs)
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays", default="_docx/sept_replays.pkl")
    ap.add_argument("--src", required=True)
    ap.add_argument("--seat", type=int, required=True)
    ap.add_argument("--base", default="main.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bare", action="store_true",
                    help="只输出裸表（不套修复层），用于对照")
    args = ap.parse_args()

    with open(args.replays, "rb") as fh:
        raw = pickle.load(fh)
    rep = json.loads(raw[args.src])
    steps = rep["steps"]
    name = rep["info"]["Agents"][args.seat]["Name"]

    # 正确错位：第 t 回合执行录像里 index t+1 的动作
    table = []
    for t in range(len(steps) - 1):
        idx = t + ACTION_SHIFT
        a = steps[idx][args.seat].get("action") if idx < len(steps) else None
        table.append(norm(a))
    while len(table) < 720:
        table.append(dict(PASS))

    if args.bare:
        src = ('"""裸动作表：来自 episode {eid} 座位 {seat}（{name}）。"""\n'
               '_TABLE = {table}\n\n\n'
               'def agent(obs):\n'
               '    t = int(obs.get("step", 0) or 0)\n'
               '    return _TABLE[t] if 0 <= t < len(_TABLE) else {pass_}\n'
               ).format(eid=args.src, seat=args.seat, name=name,
                        table=repr(table), pass_=PASS)
    else:
        with open(args.base, encoding="utf-8") as fh:
            src = fh.read().lstrip("\ufeff")
        src += OVERRIDE.format(eid=args.src, seat=args.seat, name=name,
                               table=repr(table))

    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src)
    nz = sum(1 for e in table if e["farmer"] != ["PASS"] or e["market"] or e["hands"])
    print(f"写入 {args.out}：{len(src):,} 字符，表长 {len(table)}，非空回合 {nz}")


if __name__ == "__main__":
    main()
