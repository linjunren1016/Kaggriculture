"""
Validation episode: exactly what Kaggle runs when you upload a submission.

From the official Evaluation page:
  "When you upload a submission, a Validation Episode is run where your agent
   plays against a copy of itself to ensure it runs without errors. If the
   episode fails, the submission is marked as Error."

This script replicates that check locally so a broken submission is never
uploaded. Any exception escaping the agent fails the episode and marks the
submission as Error, which is why main.py wraps itself in a safety net.

Usage:
    python validate_submission.py
    python validate_submission.py --archive submission.tar.gz
"""
import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import zipfile

with contextlib.redirect_stderr(io.StringIO()):
    from kaggle_environments import make


def run_self_play(agent_spec, seeds=(1000, 1001), steps=720):
    """Return (ok, details) for a self-play validation across several seeds."""
    results = []
    for seed in seeds:
        env = make("kaggriculture",
                   configuration={"episodeSteps": steps, "seed": seed}, debug=True)
        env.run([agent_spec, agent_spec])
        final = env.steps[-1]
        statuses = [s.status for s in final]
        rewards = [float(s.reward or 0) for s in final]
        ok = all(st == "DONE" for st in statuses)
        results.append({"seed": seed, "statuses": statuses, "rewards": rewards, "ok": ok})
    return all(r["ok"] for r in results), results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default=None,
                    help="tar.gz/zip submission to verify; default checks main.py in cwd")
    args = ap.parse_args()

    if args.archive:
        workdir = tempfile.mkdtemp(prefix="kaggval_")
        import tarfile
        with tarfile.open(args.archive) as tf:
            names = tf.getnames()
            tf.extractall(workdir)
        print(f"extracted archive to {workdir}")
        print(f"archive members: {names}")
        # Kaggle requires main.py at the archive ROOT, not in a subdirectory.
        spec = os.path.join(workdir, "main.py")
        if "main.py" not in names:
            print("FAIL: archive has no main.py at its root")
            return 1
    else:
        spec = "main.py"

    print(f"validating: {spec}")
    ok, results = run_self_play(spec)
    for r in results:
        print(f"  seed {r['seed']}: statuses={r['statuses']} rewards={r['rewards']} "
              f"{'OK' if r['ok'] else 'FAILED'}")
    print("\nRESULT:", "PASS - safe to upload" if ok else "FAIL - do not upload")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
