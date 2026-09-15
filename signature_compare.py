"""
把 V38（以及其它候选）的行为签名用与「回放 agent」相同的口径测出来，
做精确对照。回放 agent 的签名见 _docx/top_profiles.txt。

回放 agent 平均签名（8 个，均为同一路线）：
  移动 45.1%  浇水 13.7%  种植 2.6%  收获 5.4%  施肥 1.2%
  照料 4.5%   挖草 0.4%   PASS 14.7%
  市场：HIRE 265  SELL 189  BUY_PRODUCT 178  BUY_SEED 34  BUY_ANIMAL 8  BUY_LAND 2
"""
import contextlib
import io
import statistics
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")
MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}

TARGET = {"move": 0.451, "water": 0.137, "plant": 0.026, "harvest": 0.054,
          "fert": 0.012, "care": 0.045, "dig": 0.004, "pass": 0.147}
TARGET_MARKET = {"HIRE": 265, "SELL": 189, "BUY_PRODUCT": 178,
                 "BUY_SEED": 34, "BUY_ANIMAL": 8, "BUY_LAND": 2}


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


def profile(path, seeds):
    fn = load(path)
    ops = Counter()
    market = Counter()
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([fn, "pass"])
        for st in env.steps:
            a = st[0].action
            if not a:
                continue
            f = a.get("farmer")
            if isinstance(f, list) and f:
                ops[f[0]] += 1
            for h in a.get("hands") or []:
                if isinstance(h, list) and h:
                    ops[h[0]] += 1
            for mk in a.get("market") or []:
                market[mk[0]] += 1
    n = len(seeds)
    tot = sum(ops.values())
    d = {
        "move": sum(v for k, v in ops.items() if k in MOVE) / tot,
        "water": ops.get("WATER", 0) / tot,
        "plant": ops.get("PLANT", 0) / tot,
        "harvest": ops.get("HARVEST", 0) / tot,
        "fert": ops.get("FERTILIZE", 0) / tot,
        "care": ops.get("CARE", 0) / tot,
        "dig": ops.get("DIG", 0) / tot,
        "pass": ops.get("PASS", 0) / tot,
    }
    mk = {k: v / n for k, v in market.items()}
    return d, mk, tot / n


SEEDS = [960000, 960001, 960002]
out = ["候选 vs 顶尖回放 agent 的行为签名对照", ""]
hdr = (f"{'agent':<14} {'移动':>7} {'浇水':>7} {'种植':>7} {'收获':>7} "
       f"{'施肥':>7} {'照料':>7} {'挖草':>7} {'PASS':>7}")
out.append(hdr)
out.append("-" * len(hdr))
out.append(f"{'顶尖层(回放)':<14} " + " ".join(f"{TARGET[k]:>7.1%}" for k in
           ("move", "water", "plant", "harvest", "fert", "care", "dig", "pass")))

results = {}
for name, path in [("V38", "candidates/V38.py"),
                   ("C94", "candidates/C94.py"),
                   ("C95", "candidates/C95.py"),
                   ("KaitoV27", "candidates/V27.py"),
                   ("closer_cleo", "opponents_src/closer_cleo.py")]:
    try:
        d, mk, per = profile(path, SEEDS)
    except Exception as exc:
        out.append(f"{name:<14} 失败 {type(exc).__name__}: {exc}")
        continue
    results[name] = (d, mk)
    out.append(f"{name:<14} " + " ".join(f"{d[k]:>7.1%}" for k in
               ("move", "water", "plant", "harvest", "fert", "care", "dig", "pass")))

out.append("")
out.append("市场订单（每局次数）")
mh = f"{'agent':<14} " + " ".join(f"{k:>12}" for k in TARGET_MARKET)
out.append(mh)
out.append("-" * len(mh))
out.append(f"{'顶尖层(回放)':<14} " + " ".join(f"{v:>12.0f}" for v in TARGET_MARKET.values()))
for name, (d, mk) in results.items():
    out.append(f"{name:<14} " + " ".join(f"{mk.get(k, 0):>12.0f}" for k in TARGET_MARKET))

out.append("")
out.append("=== 与顶尖层的行为签名偏差（越小越接近；各项绝对差之和）===")
for name, (d, mk) in results.items():
    gap = sum(abs(d[k] - TARGET[k]) for k in TARGET)
    out.append(f"  {name:<14} {gap:>7.3f}")

text = "\n".join(out)
with open("_docx/signature_compare.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
