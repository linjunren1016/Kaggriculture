"""
作物配比实验：参数化 TARGET_MIX，在留出种子上严格对比。

背景
----
快速试探显示把小麦/甜瓜占比对调（0.34/0.24 → 0.24/0.34）后，
在开发种子上资金从 ~$25,754 升到 ~$28,610。但那批种子已反复使用，
必须在全新种子上复验。

用法：
    python mix_experiment.py --episodes 12 --seed-base 11000
"""
import argparse
import contextlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")

BASE_MIX = [
    ("WHEAT", 0.34), ("MELON", 0.24), ("CARROT", 0.22),
    ("TOMATO", 0.12), ("STRAWBERRY", 0.08),
]

CANDIDATES = {
    "当前     m.40/t.20": [
        ("WHEAT", 0.18), ("MELON", 0.40), ("CARROT", 0.14),
        ("TOMATO", 0.20), ("STRAWBERRY", 0.08),
    ],
    "甜瓜60   无番茄草莓": [
        # ZZWD_ 线上配方的方向：零番茄零草莓，甜瓜 60%
        ("WHEAT", 0.25), ("MELON", 0.60), ("CARROT", 0.15),
        ("TOMATO", 0.0), ("STRAWBERRY", 0.0),
    ],
    "甜瓜55   无番茄草莓": [
        ("WHEAT", 0.28), ("MELON", 0.55), ("CARROT", 0.17),
        ("TOMATO", 0.0), ("STRAWBERRY", 0.0),
    ],
    "甜瓜60   留草莓": [
        ("WHEAT", 0.22), ("MELON", 0.60), ("CARROT", 0.13),
        ("TOMATO", 0.0), ("STRAWBERRY", 0.05),
    ],
}


def run_cfg(mix, seeds, steps):
    for m in list(sys.modules):
        if m == "main":
            del sys.modules[m]
    import main
    main.TARGET_MIX = [tuple(x) for x in mix]

    outs = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": steps, "seed": seed}, debug=False)
        env.run([main.agent, "pass"])
        outs.append(float(env.steps[-1][0].reward or 0.0))
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=12)
    ap.add_argument("--seed-base", type=int, default=11000)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    seeds = [args.seed_base + i for i in range(args.episodes)]
    lines = [f"作物配比实验（全新种子 {seeds[0]}–{seeds[-1]}，{len(seeds)} 个）", ""]

    results = {}
    for name, mix in CANDIDATES.items():
        outs = run_cfg(mix, seeds, args.steps)
        results[name] = outs
        lines.append(f"{name:<26} 平均 ${statistics.mean(outs):>9,.0f}  "
                     f"最低 ${min(outs):>9,.0f}  最高 ${max(outs):>9,.0f}")

    base_name = "当前     m.40/t.20"
    base = results[base_name]
    lines.append("")
    lines.append(f"相对{base_name}：")
    for name, outs in results.items():
        if name == base_name:
            continue
        delta = statistics.mean(outs) - statistics.mean(base)
        wins = sum(1 for b, o in zip(base, outs) if o > b)
        verdict = "占优" if wins >= len(seeds) * 0.7 else (
            "劣势" if wins <= len(seeds) * 0.3 else "无差异")
        lines.append(f"  {name:<26} {delta:>+9,.0f}  "
                     f"({delta/statistics.mean(base)*100:+.1f}%)  胜出 {wins}/{len(seeds)}  → {verdict}")

    with open("_docx/mix_exp.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
