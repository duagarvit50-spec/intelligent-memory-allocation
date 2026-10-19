"""Reads results/runs.csv and results/frag_timeline.csv -> summary tables + figures.
Usage: python analyze.py --in results --out results/figs"""
import argparse, os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", default="results")
ap.add_argument("--out", default="results/figs")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
runs = pd.read_csv(os.path.join(a.inp, "runs.csv"))
tl = pd.read_csv(os.path.join(a.inp, "frag_timeline.csv"))
order = ["first", "best", "worst", "next", "adaptive"]
points = [p for p in ["small", "medium", "large"] if p in runs.point.unique()]
metrics = ["fail_rate", "fail_due_to_frag", "steps_per_alloc", "ns_per_alloc",
           "mean_ext_frag", "mean_free_blocks", "mean_util"]

# 1) summary table: mean and std over seeds
g = runs.groupby(["point", "strategy"])[metrics].agg(["mean", "std"])
g.to_csv(os.path.join(a.inp, "summary.csv"))
with open(os.path.join(a.inp, "summary.md"), "w") as f:
    for p in points:
        f.write(f"\n### Operating point: {p}\n\n| strategy | fail rate | steps/alloc | ns/alloc | ext. frag | free blocks |\n|---|---|---|---|---|---|\n")
        for s in order:
            r = g.loc[(p, s)]
            f.write(f"| {s} | {r[('fail_rate','mean')]:.4f} ± {r[('fail_rate','std')]:.4f} "
                    f"| {r[('steps_per_alloc','mean')]:.1f} ± {r[('steps_per_alloc','std')]:.1f} "
                    f"| {r[('ns_per_alloc','mean')]:.0f} ± {r[('ns_per_alloc','std')]:.0f} "
                    f"| {r[('mean_ext_frag','mean')]:.3f} ± {r[('mean_ext_frag','std')]:.3f} "
                    f"| {r[('mean_free_blocks','mean')]:.1f} |\n")

# 2) grouped bar charts per metric across operating points
labels = {"fail_rate": "Allocation failure rate", "steps_per_alloc": "Free-list nodes examined per allocation",
          "mean_ext_frag": "Mean external fragmentation", "ns_per_alloc": "Mean time per allocation (ns)"}
for m, title in labels.items():
    fig, ax = plt.subplots(figsize=(7, 4))
    w = 0.16
    for i, s in enumerate(order):
        means = [runs[(runs.point == p) & (runs.strategy == s)][m].mean() for p in points]
        stds = [runs[(runs.point == p) & (runs.strategy == s)][m].std() for p in points]
        ax.bar([x + i * w for x in range(len(points))], means, w, yerr=stds, label=s, capsize=2)
    ax.set_xticks([x + 2 * w for x in range(len(points))]); ax.set_xticklabels(points)
    ax.set_ylabel(title); ax.set_xlabel("Operating point"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(a.out, f"bar_{m}.png"), dpi=200); plt.close(fig)

# 3) fragmentation over time (seed-averaged) per operating point
for p in points:
    fig, ax = plt.subplots(figsize=(7, 4))
    for s in order:
        d = tl[(tl.point == p) & (tl.strategy == s)].groupby("tick").ext_frag.mean()
        ax.plot(d.index, d.values, label=s, linewidth=1)
    ax.set_xlabel("Tick"); ax.set_ylabel("External fragmentation"); ax.set_title(f"Fragmentation over time ({p})")
    ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(os.path.join(a.out, f"timeline_{p}.png"), dpi=200); plt.close(fig)

# 4) trade-off scatter: cost vs failure
fig, ax = plt.subplots(figsize=(6, 4))
for s in order:
    d = runs[runs.strategy == s]
    ax.scatter(d.steps_per_alloc, d.fail_rate, label=s, s=18)
ax.set_xlabel("Steps per allocation"); ax.set_ylabel("Failure rate"); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(a.out, "tradeoff.png"), dpi=200)

# 5) paired comparison adaptive vs each baseline (per point/seed)
piv = runs.pivot_table(index=["point", "seed"], columns="strategy", values="fail_rate")
for b in ["first", "best", "next"]:
    diff = (piv["adaptive"] - piv[b]).groupby("point").agg(["mean", "std"])
    print(f"\nadaptive - {b} (fail_rate, negative = adaptive better):\n{diff}")
print("\nWrote summary.csv, summary.md and figures to", a.out)
