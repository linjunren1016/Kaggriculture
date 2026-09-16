"""真实整局反事实验证 (counterfactual on a complete real episode).

思路
----
旧方法（replay_to_agent）把回放里对手的动作重建成一个「开放环」agent，
再放到**中立地图**上与 V38 对打 —— 对手脱离了它原本的市场环境，
实力被严重削弱，于是 V38 打谁都是 100% 胜率，结论不可用。

本方法保留**整局**：
  1. 取一局真实线上回放（含种子 seed，决定地图/商店/杂草随机数）；
  2. 我方候选 agent 占一个座位实时决策；
  3. 对手座位**逐步喂回它自己在这一局里真实打出的动作**（含全部市场挂单）；
  4. 两边共享同一个市场，因此我的挂单会真实地影响对手的价格与成交；
  5. 打满 720 回合，比最终资金。

这样对手的宏观安排（种植节奏、市场挂单时机、卖价踩点）原样保留，
只是不能再针对我做出反应 —— 这是「用真实对手轨迹做压力测试」的
最接近线上的一步，比中立地图重建严谨得多。

录像动作错位（重要）
--------------------
实测发现：这些回放 JSON 里 `steps[t].observation` 是第 t 回合**开始前**的状态
（和本地 env 一致），但 `steps[t].action` 是**产生**该观测的那次动作 ——
也就是动作数组整体比观测数组晚一格。
证据（episode 107983407，step 0 双方都 PASS，step 1 观测里却已经有
WHEAT 20 在棚里、钱 2417）。
把动作按 `t+1` 取用后，整局资金 **逐位复现**：
重放 89,152 / 88,935  ==  录像 89,152 / 88,935（shift=0 只有 55,959 / 55,851）。
所以喂回时必须用 `ACTION_SHIFT = 1`；自检就是用来钉死这一点的。

自检
----
`--selfcheck` 把**双方**都替换成各自的录像动作，跑一遍。
若最终资金与回放记录完全一致，说明种子/配置可复现、喂回机制无误；
不一致则后面所有结论都不成立。

用法
----
python cf_real.py --selfcheck
python cf_real.py --cand candidates/V38.py --cand main.py
"""
import argparse
import contextlib
import io
import json
import os
import pickle
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")

PASS = {"farmer": ["PASS"], "hands": [], "market": []}

# 动作数组相对观测数组的错位量，见模块 docstring。
ACTION_SHIFT = 1


# ---------------------------------------------------------------- 回放

def load_replays(path):
    """返回 {episode_id: replay_dict}。支持 .pkl(JSON 字符串) / .json / 目录。"""
    out = {}
    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(path, name), encoding="utf-8") as fh:
                r = json.load(fh)
            out[str(r.get("info", {}).get("EpisodeId") or name)] = r
        return out

    if path.endswith(".pkl") or path.endswith(".pickle"):
        with open(path, "rb") as fh:
            raw = pickle.load(fh)
        for k, v in raw.items():
            out[str(k)] = json.loads(v) if isinstance(v, str) else v
        return out

    with open(path, encoding="utf-8") as fh:
        r = json.load(fh)
    out[str(r.get("info", {}).get("EpisodeId") or "single")] = r
    return out


def replay_index(replay):
    """抽出种子、逐步双座位动作表、回放记录的最终资金。"""
    seed = replay.get("info", {}).get("seed")
    cfg = replay.get("configuration", {}) or {}
    steps = replay.get("steps", [])
    acts = {}
    for t, row in enumerate(steps):
        acts[t] = [(entry or {}).get("action") for entry in row]
    final = steps[-1] if steps else []
    banks = []
    for entry in final:
        obs = (entry or {}).get("observation", {}) or {}
        farms = obs.get("farms", []) or []
        me = obs.get("player", 0)
        banks.append(farms[me]["money"] if me < len(farms) else None)
    names = [a.get("Name") for a in replay.get("info", {}).get("Agents", [])]
    return {
        "seed": seed,
        "acts": acts,
        "banks": banks,
        "names": names,
        "episode_id": replay.get("info", {}).get("EpisodeId"),
        "config": cfg,
    }


def recorded_agent(acts, seat, stats=None, shift=ACTION_SHIFT):
    """把某一座位在回放里的动作原样喂回。"""
    def fn(obs):
        t = obs.get("step", 0) + shift
        row = acts.get(t)
        a = row[seat] if row and seat < len(row) else None
        if not isinstance(a, dict):
            return dict(PASS)
        out = {
            "farmer": a.get("farmer", ["PASS"]),
            "hands": a.get("hands", []) or [],
            "market": a.get("market", []) or [],
        }
        if stats is not None:
            stats["moves"] = stats.get("moves", 0) + 1
            if out["market"]:
                stats["mkt"] = stats.get("mkt", 0) + len(out["market"])
        return out
    fn.__name__ = "recorded_seat_%d" % seat
    return fn


# ---------------------------------------------------------------- 运行

def run_episode(seed, cfg, agent_a, agent_b, steps=720):
    conf = {"episodeSteps": steps, "seed": seed}
    for k in ("boardSize", "startingMoney", "shedCapacity", "turnsPerDay",
              "farmHandCostMult", "marketParams", "maxMarketOrdersPerTurn",
              "townCenterSellInterval", "townShopSellInterval",
              "townShopUnlockInterval", "weedSpawnChance"):
        if cfg.get(k) is not None:
            conf[k] = cfg[k]
    env = make("kaggriculture", configuration=conf, debug=False)
    env.run([agent_a, agent_b])
    final = env.steps[-1]
    rewards = [float(s.reward or 0) for s in final]
    statuses = [s.status for s in final]
    return rewards, statuses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays", default="_docx/sept_replays.pkl")
    ap.add_argument("--cand", action="append", default=[],
                    help="候选 agent 路径，可重复")
    ap.add_argument("--limit", type=int, default=0, help="只用前 N 局")
    ap.add_argument("--selfcheck", action="store_true",
                    help="双方都用录像动作，验证可复现")
    ap.add_argument("--out", default="_docx/cf_real.txt")
    args = ap.parse_args()

    reps = load_replays(args.replays)
    items = sorted(reps.items(), key=lambda kv: kv[0])
    if args.limit:
        items = items[: args.limit]

    lines = []

    # ---------------- 自检
    if args.selfcheck:
        lines.append("自检：双方均用录像动作重放，对比回放记录资金")
        lines.append("")
        ok = bad = 0
        for eid, rep in items:
            idx = replay_index(rep)
            if idx["seed"] is None:
                lines.append(f"  {eid}  无 seed，跳过")
                continue
            mins = idx["acts"][0]  # noqa: F841  (占位：确认动作表非空)
            a = recorded_agent(idx["acts"], 0)
            b = recorded_agent(idx["acts"], 1)
            r, st = run_episode(idx["seed"], idx["config"], a, b)
            want = idx["banks"]
            match = all(abs(r[i] - (want[i] or 0)) < 1e-6 for i in range(2))
            ok += match
            bad += (not match)
            flag = "一致" if match else "不一致"
            lines.append(
                f"  {eid} seed={idx['seed']:<12} 重放 {r[0]:>10,.0f} / {r[1]:>10,.0f}"
                f"   记录 {want[0]:>10,.0f} / {want[1]:>10,.0f}   {flag}  {st}")
        lines.append("")
        lines.append(f"一致 {ok} 局，不一致 {bad} 局")
        text = "\n".join(lines)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(text)
        return 0 if bad == 0 else 1

    # ---------------- 正式
    if not args.cand:
        print("需要 --cand 或 --selfcheck")
        return 2
    cands = {}
    for p in args.cand:
        with open(p, encoding="utf-8") as fh:
            src = fh.read().lstrip("\ufeff")
        cands[p] = get_last_callable(src, path=p)

    for cp, cfn in cands.items():
        lines.append(f"候选 = {cp}   对手轨迹来源 = {args.replays}（{len(items)} 局）")
        lines.append("")
        lines.append("  episode      对手         座位   我方资金     对手资金     结果    分差")
        win = lose = tie = 0
        for eid, rep in items:
            idx = replay_index(rep)
            if idx["seed"] is None:
                lines.append(f"  {eid}  无 seed，跳过")
                continue
            for opp_seat in (0, 1):
                my_seat = 1 - opp_seat
                opp = recorded_agent(idx["acts"], opp_seat)
                pair = [None, None]
                pair[my_seat] = cfn
                pair[opp_seat] = opp
                r, st = run_episode(idx["seed"], idx["config"], pair[0], pair[1])
                mine, theirs = r[my_seat], r[opp_seat]
                if "DONE" not in st:
                    res = "异常"
                elif mine > theirs:
                    res = "胜"
                    win += 1
                elif mine < theirs:
                    res = "负"
                    lose += 1
                else:
                    res = "平"
                    tie += 1
                lines.append(
                    f"  {eid:<12} seat{opp_seat}({idx['names'][opp_seat][:12]:<12})"
                    f" 我座{my_seat}  {mine:>10,.0f}  {theirs:>10,.0f}   {res}  "
                    f"{mine - theirs:>+10,.0f}")
        n = win + lose + tie
        lines.append("")
        lines.append(f"合计 {win}胜 {lose}负 {tie}平   胜率 {win / n:.1%}" if n else "无有效对局")
        lines.append("")

    text = "\n".join(lines)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
