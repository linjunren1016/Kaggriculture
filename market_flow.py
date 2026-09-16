"""统计录像里高分 agent 的市场指令结构 —— 区分「卖出自家产出」与「低买高卖的来回交易」。"""
import collections
import json
import pickle
import sys

sept = sys.argv[1] if len(sys.argv) > 1 else "108035195"
seat = int(sys.argv[2]) if len(sys.argv) > 2 else 0

raw = pickle.load(open("_docx/sept_replays.pkl", "rb"))
rep = json.loads(raw[sept])
steps = rep["steps"]

buy = collections.Counter()
sell = collections.Counter()
nb = ns = 0
for t in range(720):
    entry = steps[t][seat]
    a = entry.get("action")
    if not isinstance(a, dict):
        continue
    for m in a.get("market") or []:
        if not isinstance(m, list) or len(m) < 3:
            continue
        if m[0] == "BUY_PRODUCT":
            buy[m[1]] += m[2]
            nb += 1
        elif m[0] == "SELL":
            sell[m[1]] += m[2]
            ns += 1

# 观测到的产出（收获次数）作为对照
harv = 0
for t in range(720):
    a = steps[t][seat].get("action")
    if not isinstance(a, dict):
        continue
    for u in [a.get("farmer")] + list(a.get("hands") or []):
        if isinstance(u, list) and u and u[0] == "HARVEST":
            harv += 1

L = []
L.append(f"episode {sept} seat {seat}  ({rep['info']['Agents'][seat]['Name']})")
L.append(f"回放终局资金 {rep['steps'][-1][seat]['observation']['farms'][seat]['money']:,.0f}")
L.append(f"HARVEST 次数 {harv}")
L.append("")
L.append("商品      BUY_PRODUCT 单位     SELL 单位     净买入")
for k in sorted(set(list(buy) + list(sell))):
    L.append(f"{k:<12}{buy[k]:>14,}{sell[k]:>14,}{buy[k]-sell[k]:>12,}")
L.append("")
L.append(f"BUY_PRODUCT 指令 {nb} 条，共 {sum(buy.values()):,} 单位")
L.append(f"SELL       指令 {ns} 条，共 {sum(sell.values()):,} 单位")

# 逐日：交易量 vs 资金增加
L.append("")
L.append(" day  当日BUY单位  当日SELL单位   日终资金   资金增量")
prev = None
for d in range(30):
    b = s = 0
    for t in range(d * 24, d * 24 + 24):
        a = steps[t][seat].get("action")
        if not isinstance(a, dict):
            continue
        for m in a.get("market") or []:
            if not isinstance(m, list) or len(m) < 3:
                continue
            if m[0] == "BUY_PRODUCT":
                b += m[2]
            elif m[0] == "SELL":
                s += m[2]
    money = steps[d * 24 + 23][seat]["observation"]["farms"][seat]["money"]
    inc = "" if prev is None else f"{money - prev:>+10,.0f}"
    L.append(f"{d:>4}{b:>13,}{s:>14,}{money:>12,.0f}{inc:>12}")
    prev = money

text = "\n".join(L)
open("_docx/market_flow.txt", "w", encoding="utf-8").write(text)
print(text)
