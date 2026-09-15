"""
从线上回放提取某个玩家的完整动作序列，生成"固定动作表"Agent。

用途
----
线上遇到的强对手（如 ZZDW_）是固定动作序列，连打多局开局完全一致。
把它的动作表提取出来在本地复现，就有了一个**真正打赢过我们的对手**做陪练 ——
比自建陪练有说服力得多。

这也是文档里描述的"固定动作表"打法：按当前 step 直接查表返回动作。

用法：
    python extract_agent.py --replay replays/episode-109170440-replay.json \
        --player 0 --name ZZDW --out opponents/zzdw.py
"""
import argparse
import json
import os
import sys


def extract(path, player):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    steps = d["steps"]
    table = []
    for st in steps:
        act = st[player].get("action")
        if act is None:
            table.append(None)
        else:
            # 规范化：farmer 必须是 list，hands 是 list of list
            farmer = act.get("farmer")
            if isinstance(farmer, str):
                farmer = [farmer]
            hands = [h if isinstance(h, list) else [h]
                     for h in (act.get("hands") or [])]
            market = [list(m) for m in (act.get("market") or [])]
            table.append({"farmer": farmer or ["PASS"],
                          "hands": hands,
                          "market": market})
    info = d.get("info", {})
    names = [a.get("Name") for a in info.get("Agents", [])]
    return table, names, d.get("rewards", []), info.get("seed")


TEMPLATE = '''"""
自动生成：复现线上对手 {name} 的固定动作序列。

来源回放：{replay}
该局结果：{names[0]}={r0:,.0f}  vs  {names[1]}={r1:,.0f}   seed={seed}
表中动作数：{n}

这是"固定动作表"打法：按当前 step 查表返回动作，不做任何自适应。
仅用于本地评测，不提交。

注意：动作表只对生成它的那张地图最优。换 seed 后布局不同，
它的表现会下降 —— 这正是固定序列的固有弱点。
"""
import functools

# 719 步的动作表；None 表示回放里该步没有记录（用 PASS 兜底）
_TABLE = {table}


def _norm(op):
    return [op] if isinstance(op, str) else list(op)


@functools.wraps(lambda obs: None)
def agent(obs):
    step = obs.get("step", 0)
    entry = _TABLE.get(step)
    if entry is None:
        return {{"farmer": ["PASS"], "hands": [], "market": []}}
    return {{"farmer": _norm(entry["farmer"]),
             "hands": [_norm(h) for h in entry["hands"]],
             "market": [list(m) for m in entry["market"]]}}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", required=True)
    ap.add_argument("--player", type=int, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    table, names, rewards, seed = extract(args.replay, args.player)
    idx = {i: a for i, a in enumerate(table) if a is not None}
    print(f"提取到 {len(idx)} 步动作（共 {len(table)} 步）")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    src = TEMPLATE.format(
        name=args.name, replay=args.replay, names=names,
        r0=rewards[0] if len(rewards) > 0 else 0,
        r1=rewards[1] if len(rewards) > 1 else 0,
        seed=seed, n=len(idx), table=repr(idx),
    )
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(src)
    print(f"已写出 {args.out}")

    # 自检：能否导入
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_agent", args.out)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    a = mod.agent({"step": 1})
    print(f"自检 step1 动作: {a}")


if __name__ == "__main__":
    sys.exit(main())
