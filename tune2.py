"""
参数扫描：直接改 main.py 的模块级常量，测不同配置的绝对表现。

用「对 pass 的绝对资金」作为指标 —— 因为胜负全胜没有区分度，
绝对资金才能反映改动好坏（官方评分只看胜负，但线下要先用资金做梯度信号）。

用法：
    python tune2.py --sweep HIRE_CAP --values 4,6,8,10 --episodes 3
"""
import argparse
import contextlib
import importlib
import io
import statistics
import sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

sys.path.insert(0, ".")


def run_once(param, value, seeds, steps):
    """每个配置都重新导入 main，避免 lru_cache 等状态残留。"""
    for m in list(sys.modules):
        if m == "main":
            del sys.modules[m]
    import main
    setattr(main, param, value)

    outs = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": steps, "seed": seed}, debug=False)
        env.run([main.agent, "pass"])
        outs.append(float(env.steps[-1][0].reward or 0.0))
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--param", default="HIRE_CAP")
    ap.add_argument("--values", default="4,6,8,10")
    ap.add_argument("--episodes", type=int, default=3)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    values = [int(v) if v.lstrip("-").isdigit() else v for v in args.values.split(",")]
    seeds = [4000 + i for i in range(args.episodes)]

    lines = [f"扫描 {args.param}（对 pass，种子 {seeds}）", "",
             f"{'取值':>8}  {'平均资金':>12}  {'最低':>12}  {'最高':>12}"]
    results = []
    for v in values:
        outs = run_once(args.param, v, seeds, args.steps)
        results.append((v, statistics.mean(outs)))
        lines.append(f"{str(v):>8}  {statistics.mean(outs):>12,.0f}  "
                     f"{min(outs):>12,.0f}  {max(outs):>12,.0f}")

    best = max(results, key=lambda r: r[1])
    lines.append("")
    lines.append(f"最佳 {args.param} = {best[0]}（平均 {best[1]:,.0f}）")

    with open("_docx/tune2.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("done")


if __name__ == "__main__":
    sys.exit(main())
