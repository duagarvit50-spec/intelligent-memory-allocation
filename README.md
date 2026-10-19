# Intelligent Memory Allocation - code and data

Files
- alloc_sim.py      simulator: First/Best/Worst/Next Fit + adaptive, workload generator, metrics
- config.json       operating points, size distribution, adaptive thresholds
- tune_adaptive.py  threshold grid search on separate seeds (100+)
- analyze.py        tables (summary.csv/.md) and figures from the raw CSVs
- results/          raw CSVs: runs.csv, frag_timeline.csv, trace_*.csv

Run order
1. pip install -r requirements.txt
2. python tune_adaptive.py            # optional; copy best values into config.json
3. python alloc_sim.py --seeds 5 --out results
4. python analyze.py

Metrics: steps/alloc = free-list nodes examined; ext. frag = 1 - largest free / total free;
fail_due_to_frag = total free >= request but no single block fits.
Hardware/software used: (fill in CPU, RAM, OS, Python version)
