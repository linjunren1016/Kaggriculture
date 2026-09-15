"""Watch a single wheat plant's tile dict evolve over its life, plus market prices."""
import contextlib, io, json, sys

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make

CROP = sys.argv[1] if len(sys.argv) > 1 else "WHEAT"
STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 120


def probe(obs):
    """Plant at step 0 on the farmer's tile, then water daily; report the tile."""
    me = obs["farms"][obs["player"]]
    fx, fy = me["farmer"]
    tile = me["tiles"][fy][fx]
    market = []
    if obs["step"] == 0:
        market.append(["BUY_SEED", CROP, 1])
    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        if not tile.get("watered_today"):
            return {"farmer": ["WATER"], "hands": [], "market": market}
        return {"farmer": ["PASS"], "hands": [], "market": market}
    if tile is None and obs["private"]["seeds"].get(CROP, 0) > 0:
        return {"farmer": ["PLANT", CROP], "hands": [], "market": market}
    return {"farmer": ["PASS"], "hands": [], "market": market}


env = make("kaggriculture", configuration={"episodeSteps": STEPS, "seed": 1000}, debug=False)
env.run([probe, "pass"])

seen = None
for i, st in enumerate(env.steps):
    obs = st[0].observation
    me = obs["farms"][0]
    fx, fy = me["farmer"]
    tile = me["tiles"][fy][fx]
    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        key = (obs["day"], obs["hour"])
        print(f"day {obs['day']:>2} hour {obs['hour']:>2} | {json.dumps(tile)}")
    elif isinstance(tile, dict) and tile.get("kind") == "WEED":
        print(f"day {obs['day']:>2} hour {obs['hour']:>2} | BECAME WEED")
        break
