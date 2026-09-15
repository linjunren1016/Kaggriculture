"""
交易频率对齐实验：调 V38 的 _preempt_shift（提前卖出）层。

动机（来自官方 9 月 meta 统计）：
  9 月顶尖层每局 SELL 400.8 次、BUY_SEED 177.2 次
  V38 每局 SELL 505 次（多 26%）、BUY_SEED 105 次（少 41%）
  V38 的额外卖单来自 _preempt_shift —— 把「未来的卖单」提前到现在。

做法：直接改 V38 模块里的 _PREEMPT_* 常量（不改文件，保持哈希可验证），
分别在多子集种子上测：
  - 每局 SELL 次数（是否更接近 9 月 meta）
  - 终局资金
  - 与基线 V38 的对战胜负（同种子，直接比较）

用法：
    python preempt_exp.py --configs baseline,no_preempt,batch6,batch3 --episodes 4
"""
import argparse
import contextlib
import importlib.util
import io
import os
import statistics
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")

CONFIGS = {
    "baseline":  {},                                      # 原样
    "no_preempt": {"_PREEMPT_ENABLED": False},            # 关闭提前卖出
    "batch6":    {"_PREEMPT_MAX_BATCH": 6},               # 减半
    "batch2":    {"_PREEMPT_MAX_BATCH": 2},               # 大幅减少
    "minq12":    {"_PREEMPT_MIN_FUTURE_QUANTITY": 12},    # 只对大量卖单提前
    "short":     {"_PREEMPT_STOP": 400},                  # 缩短作用窗口
}


def load_v38():
    spec = importlib.util.spec_from_file_location("v38mod", "candidates/V38.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def apply_cfg(mod, cfg):
    """恢复默认再套用配置。"""
    defaults = {
        "_PREEMPT_ENABLED": True,
        "_PREEMPT_FRACTION": 1.0,
        "_PREEMPT_MAX_BATCH": 12,
        "_PREEMPT_MIN_CLONE_DISTANCE": 0,
        "_PREEMPT_MAX_CLONE_DISTANCE": 6,
        "_PREEMPT_MIN_PRICE_RATIO": 0.0,
        "_PREEMPT_MIN_FUTURE_QUANTITY": 4,
        "_PREEMPT_START": 120,
        "_PREEMPT_STOP": 680,
    }
    for k, v in defaults.items():
        if hasattr(mod, k):
            setattr(mod, k, v)
    for k, v in cfg.items():
        setattr(mod, k, v)


def profile(mod, seeds, opponent="pass"):
    sells, buys = [], []
    money = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([mod.agent, opponent])
        s = b = 0
        for st in env.steps:
            for o in ((st[0].action or {}).get("market") or []):
                if o and o[0] == "SELL":
                    s += 1
                elif o and o[0] == "BUY_SEED":
                    b += 1
        sells.append(s)
        buys.append(b)
        money.append(float(env.steps[-1][0].reward or 0))
    return (statistics.mean(sells), statistics.mean(buys),
            statistics.mean(money), money)


ap = argparse.ArgumentParser()
ap.add_argument("--configs", default="baseline,no_preempt,batch6,batch2,minq12,short")
ap.add_argument("--episodes", type=int, default=4)
ap.add_argument("--seed-base", type=int, default=990000)
args = ap.parse_args()

seeds = [args.seed_base + i for i in range(args.episodes)]
names = [c.strip() for c in args.configs.split(",") if c.strip()]

out = [f"V38 交易频率实验（种子 {seeds[0]}–{seeds[-1]}）",
       f"目标：SELL≈400.8 / BUY_SEED≈177.2（9 月 meta）", ""]
out.append(f"{'配置':<12} {'SELL/局':>9} {'BUY_SEED/局':>12} {'平均资金':>12} "
           f"{'最低':>12} {'相对基线':>11}")
out.append("-" * 72)
base_money = None
results = {}
for nm in names:
    mod = load_v38()
    apply_cfg(mod, CONFIGS.get(nm, {}))
    s, b, m, arr = profile(mod, seeds)
    results[nm] = (s, b, m, arr)
    if nm == "baseline":
        base_money = arr
    delta = ""
    if base_money is not None and len(base_money) == len(arr):
        d = statistics.mean(arr) - statistics.mean(base_money)
        w = sum(1 for x, y in zip(arr, base_money) if x > y)
        delta = f"{d:>+11,.0f} ({w}/{len(arr)})"
    out.append(f"{nm:<12} {s:>9.1f} {b:>12.1f} {m:>12,.0f} {min(arr):>12,.0f} {delta}")

out.append("")
out.append("说明：'相对基线' 是同种子下与 baseline 的平均资金差，括号内为占优种子数。")

text = "\n".join(out)
with open("_docx/preempt_exp.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
