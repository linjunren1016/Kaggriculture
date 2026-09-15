"""
把 agent 放进参考天梯评测：对 10 个参考对手各打若干局，看真实水平。

这个天梯来自公开数据集（raykkretzschmar/kaggriculture-reference-agents），
解决了"本地没有有区分度的对手"的问题 —— 内置 pass/starter/自建陪练都太弱
（全胜 = 无区分度），而这里有从 3,000 分到 164,000 分的完整分层。

参考对手的预期资金（来自 agents_manifest.csv）：
  tier0 fallow_finn      3,000      什么都不种
  tier1 wheat_walter     7,056      单农民单作物
  tier2 rotation_rosa   12,929      雇 4 人三轮作
  tier3 homestead_hana  16,030      买一块地+稳定作物
  tier4 melon_mateo     28,349      甜瓜+拒绝低价出售
  tier5 rancher_rita    46,211      牲畜规模化
  tier6 broker_bea     164,265      meta 田块计划
  tier7 ledger_lena    164,540      meta + 不同出售顺序
  tier8 slotter_silas  162,999      meta + 重排市场订单
  tier9 closer_cleo    148,546      meta + 出售重排

注意：加载参考 agent 要走 Kaggle 的"最后一个可调用对象"规则，
否则会拿到文件里最后一个 helper 函数而不是 agent。

用法：
    python ladder_eval.py --agent main.py --episodes 2
"""
import argparse
import contextlib
import io
import os
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")

BASE = "opponents_src"

MANIFEST = [
    ("fallow_finn.py", "tier0 Fallow Finn", 3000),
    ("wheat_walter.py", "tier1 Wheat Walter", 7056),
    ("rotation_rosa.py", "tier2 Rotation Rosa", 12929),
    ("homestead_hana.py", "tier3 Homestead Hana", 16030),
    ("melon_mateo.py", "tier4 Melon Mateo", 28349),
    ("rancher_rita.py", "tier5 Rancher Rita", 46211),
    ("broker_bea.py", "tier6 Broker Bea", 164265),
    ("ledger_lena.py", "tier7 Ledger Lena", 164540),
    ("slotter_silas.py", "tier8 Slotter Silas", 162999),
    ("closer_cleo.py", "tier9 Closer Cleo", 148546),
]


def load_agent(path):
    """按 Kaggle 规则加载：最后一个可调用对象。"""
    raw = open(path, encoding="utf-8").read()
    return get_last_callable(raw, path=path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="main.py")
    ap.add_argument("--episodes", type=int, default=2)
    ap.add_argument("--seed-base", type=int, default=30000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    mine = load_agent(args.agent)
    seeds = [args.seed_base + i for i in range(args.episodes)]
    lines = [f"天梯评测：{args.agent}  vs  10 个参考对手",
             f"种子 {seeds[0]}–{seeds[-1]}，双方各坐一次 → {len(seeds)*2} 局/对手", "",
             f"{'对手':<22} {'预期':>9} {'我方均':>9} {'对手均':>9} {'战绩':>9} {'胜率':>7}"]
    lines.append("-" * 76)

    total_w = total_n = 0
    for fname, label, expected in MANIFEST:
        path = os.path.join(BASE, fname)
        if not os.path.exists(path):
            lines.append(f"{label:<22} {'(文件缺失)':>9}")
            continue
        opp = load_agent(path)
        rows = []
        for seed in seeds:
            for order in (0, 1):
                env = make("kaggriculture",
                           configuration={"episodeSteps": args.steps, "seed": seed},
                           debug=False)
                env.run([mine, opp] if order == 0 else [opp, mine])
                f = env.steps[-1]
                m = float(f[0].reward or 0)
                o = float(f[1].reward or 0)
                if order == 1:
                    m, o = o, m
                if f[0].status == "DONE":
                    rows.append((m, o))
        if not rows:
            lines.append(f"{label:<22} {'(无有效对局)':>9}")
            continue
        w = sum(1 for m, o in rows if m > o)
        total_w += w
        total_n += len(rows)
        lines.append(f"{label:<22} {expected:>9,} "
                     f"{statistics.mean(m for m,_ in rows):>9,.0f} "
                     f"{statistics.mean(o for _,o in rows):>9,.0f} "
                     f"{f'{w}W-{len(rows)-w}L':>9} {w/len(rows):>7.0%}")

    lines.append("")
    if total_n:
        lines.append(f"合计 {total_w}W-{total_n-total_w}L   总胜率 {total_w/total_n:.1%}")

    text = "\n".join(lines)
    with open("_docx/ladder_eval.txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
