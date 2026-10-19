"""Grid-search adaptive thresholds on TUNING seeds (100+), separate from the
evaluation seeds (0..N) used in alloc_sim.py, to avoid overfitting.
Usage: python tune_adaptive.py --out results/tune.csv
Pick the best row, put its values in config.json["adaptive"], then rerun alloc_sim.py."""
import argparse, csv, io, itertools
import alloc_sim as A

GRID = dict(small_n=[4, 8, 16], frag_hi=[0.5, 0.7, 0.85, 0.95],
            big_frac=[0.05, 0.25, 0.5], refresh=[25, 100])

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="results/tune.csv")
ap.add_argument("--seeds", type=int, default=3)
ap.add_argument("--point", default="small")
a = ap.parse_args()
pname, n, heap, life = next(p for p in A.POINTS if p[0] == a.point)
dummy = csv.writer(io.StringIO())
traces = [A.gen_trace(n, life, 100 + s) for s in range(a.seeds)]

import os
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
rows = []
# baselines for reference
for strat in ["first", "best", "next"]:
    rs = [A.run(strat, t, heap, pname, 100 + i, dummy) for i, t in enumerate(traces)]
    rows.append(dict(config=strat, fail_rate=sum(r["fail_rate"] for r in rs)/len(rs),
                     steps=sum(r["steps_per_alloc"] for r in rs)/len(rs),
                     frag=sum(r["mean_ext_frag"] for r in rs)/len(rs)))
for combo in itertools.product(*GRID.values()):
    A.ADAPT.update(dict(zip(GRID.keys(), combo)))
    rs = [A.run("adaptive", t, heap, pname, 100 + i, dummy) for i, t in enumerate(traces)]
    rows.append(dict(config=str(dict(zip(GRID.keys(), combo))),
                     fail_rate=sum(r["fail_rate"] for r in rs)/len(rs),
                     steps=sum(r["steps_per_alloc"] for r in rs)/len(rs),
                     frag=sum(r["mean_ext_frag"] for r in rs)/len(rs)))
with open(a.out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
rows.sort(key=lambda r: (r["fail_rate"], r["steps"]))
print("Top 5 (lowest failure rate, then lowest cost):")
for r in rows[:5]: print(r)
