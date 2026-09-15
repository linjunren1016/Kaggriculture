"""
签名对照（快速版）：候选 vs 9 月 meta（当前时期）。

9 月 meta 签名来自从官方回放还原的 12 个 2,809–2,908 分 agent。
8 月 meta 签名一并列出，以便看出 meta 的演化。
"""
import contextlib
import io
import sys
from collections import Counter

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

sys.path.insert(0, ".")
MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}
KEYS = ("move", "water", "plant", "harvest", "fert", "care", "pass", "dig")
SEPT = {"move": 0.424, "water": 0.163, "plant": 0.035, "harvest": 0.070,
        "fert": 0.013, "care": 0.059, "pass": 0.074, "dig": 0.005}
AUG = {"move": 0.451, "water": 0.137, "plant": 0.026, "harvest": 0.054,
       "fert": 0.012, "care": 0.045, "pass": 0.147, "dig": 0.004}
MK = {"SELL": 400.8, "HIRE": 273.5, "BUY_SEED": 177.2,
      "BUY_PRODUCT": 66.5, "BUY_ANIMAL": 12.4, "BUY_LAND": 2.2}


def load(p):
    return get_last_callable(open(p, encoding="utf-8").read(), path=p)


def prof(path, seed=970000):
    fn = load(path)
    ops, market = Counter(), Counter()
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
        for m in a.get("market") or []:
            market[m[0]] += 1
    t = sum(ops.values()) or 1
    d = {"move": sum(v for k, v in ops.items() if k in MOVE) / t}
    for k in KEYS[1:]:
        d[k] = ops.get(k.upper(), 0) / t
    return d, dict(market)


out = ["候选 vs 9 月 meta（当前时期；种子 970000 单局口径）", ""]
hdr = f"{'agent':<13}" + "".join(f"{k:>8}" for k in KEYS) + "   偏差(9月)  (8月)"
out.append(hdr)
out.append("-" * len(hdr))
out.append(f"{'9月meta':<13}" + "".join(f"{SEPT[k]:>8.1%}" for k in KEYS) + "   基准")
out.append(f"{'8月meta':<13}" + "".join(f"{AUG[k]:>8.1%}" for k in KEYS))

rows = []
for name, p in [("V38", "candidates/V38.py"),
                ("C94", "candidates/C94.py"),
                ("C95", "candidates/C95.py"),
                ("KaitoV27", "candidates/V27.py"),
                ("closer_cleo", "opponents_src/closer_cleo.py")]:
    try:
        d, mk = prof(p)
    except Exception as exc:
        out.append(f"{name:<13} 失败 {type(exc).__name__}")
        continue
    g9 = sum(abs(d[k] - SEPT[k]) for k in KEYS)
    g8 = sum(abs(d[k] - AUG[k]) for k in KEYS)
    out.append(f"{name:<13}" + "".join(f"{d[k]:>8.1%}" for k in KEYS)
               + f"   {g9:>8.3f}  ({g8:.3f})")
    rows.append((name, mk, g9))

out.append("")
out.append("市场订单/局")
mh = f"{'agent':<13}" + "".join(f"{k:>12}" for k in MK)
out.append(mh)
out.append("-" * len(mh))
out.append(f"{'9月meta':<13}" + "".join(f"{v:>12.0f}" for v in MK.values()))
for name, mk, g9 in rows:
    out.append(f"{name:<13}" + "".join(f"{mk.get(k, 0):>12.0f}" for k in MK))

text = "\n".join(out)
with open("_docx/sept_sig.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
