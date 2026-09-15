"""
诊断：量化 main.py 的行为特征，定位结构性短板。

输出三块：
  1. 动作分布（农民 / 雇工）—— 时间花在哪
  2. 平均地块利用率 —— 产能有没有用满
  3. 资金曲线 —— 什么时候开始赚钱
跨多个种子聚合，避免单局噪声。
"""
import contextlib
import io
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

AGENT = sys.argv[1] if len(sys.argv) > 1 else "main.py"
OPP = sys.argv[2] if len(sys.argv) > 2 else "pass"
SEEDS = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [3000, 3001, 3002]

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
out = [f"诊断 {AGENT}（对手 {OPP}，种子 {SEEDS}）", ""]

agg_farmer = Counter()
agg_hand = Counter()
util_samples = []
money_curve = {}
market_counts = Counter()

for seed in SEEDS:
    env = make("kaggriculture",
               configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run([AGENT, OPP])

    for i, st in enumerate(env.steps):
        act = st[0].action
        if act:
            f = act["farmer"]
            if isinstance(f, list) and f:
                agg_farmer[f[0]] += 1
            for h in act.get("hands", []):
                if isinstance(h, list) and h:
                    agg_hand[h[0]] += 1
            for m in act.get("market", []):
                market_counts[m[0]] += 1
        # 每隔 2 天采样一次利用率
        if i % 48 == 0:
            obs = st[0].observation
            me = obs["farms"][0]
            unlocked = sum(1 for r in me["tiles"] for t in r if t != "LOCKED")
            used = sum(1 for r in me["tiles"] for t in r
                       if isinstance(t, dict) and t.get("kind") in ("PLANT", "COOP", "PASTURE"))
            if unlocked:
                util_samples.append(used / unlocked)
            day = obs["day"]
            money_curve.setdefault(day, []).append(me["money"])

out.append("=== 地块利用率（已用 / 已解锁，每 2 天采样）===")
if util_samples:
    import statistics
    out.append(f"  平均 {statistics.mean(util_samples):.1%}   "
               f"最低 {min(util_samples):.1%}   最高 {max(util_samples):.1%}")
out.append("")

out.append("=== 资金曲线（多种子平均）===")
for day in sorted(money_curve):
    vals = money_curve[day]
    out.append(f"  day {day:>2}  ${sum(vals)/len(vals):>10,.0f}")
out.append("")

ft = sum(agg_farmer.values())
ht = sum(agg_hand.values())
out.append(f"=== 农民动作（共 {ft} 次）===")
for k, v in agg_farmer.most_common(12):
    tag = "  <-移动" if k in MOVES else ""
    out.append(f"  {k:<18} {v:>6}  {v/ft:>6.1%}{tag}")
out.append("")
out.append(f"=== 雇工动作（共 {ht} 次）===")
for k, v in agg_hand.most_common(12):
    tag = "  <-移动" if k in MOVES else ""
    out.append(f"  {k:<18} {v:>6}  {v/ht:>6.1%}{tag}")

fmove = sum(v for k, v in agg_farmer.items() if k in MOVES)
hmove = sum(v for k, v in agg_hand.items() if k in MOVES)
out.append("")
out.append(f"移动占比：农民 {fmove/ft:.1%}   雇工 {hmove/ht:.1%}")
out.append("")
out.append("=== 市场订单分布 ===")
for k, v in market_counts.most_common():
    out.append(f"  {k:<18} {v:>6}")

with open("_docx/diag_main.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done")
