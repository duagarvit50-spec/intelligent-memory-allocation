# Intelligent Memory Allocation

## Project Overview

This project investigates whether an adaptive dynamic memory allocation strategy can reduce allocation cost and fragmentation compared with conventional allocation strategies.

The simulator compares five strategies: First Fit, Best Fit, Worst Fit, Next Fit, and Adaptive. Workloads with variable memory request sizes and process lifetimes are used to evaluate their performance.

## Repository Contents

- `alloc_sim.py` — Memory allocation simulator, workload generator, and metric collection.
- `config.json` — Workload operating points and adaptive policy configuration.
- `tune_adaptive.py` — Searches adaptive policy thresholds using tuning workloads.
- `analyze.py` — Generates summary tables and plots from experimental CSV files.
- `requirements.txt` — Python package dependencies.
- `runs.csv` — Per-run experimental metrics.
- `frag_timeline.csv` — Sampled fragmentation measurements over time.
- `summary.csv` and `summary.md` — Aggregated experimental results.
- `trace_*.csv` — Generated workload traces.
- `bar_*.png`, `timeline_*.png`, and `tradeoff.png` — Generated analysis figures.

## Allocation Strategies

1. **First Fit:** Selects the first free block large enough for a request.
2. **Best Fit:** Selects the smallest suitable free block.
3. **Worst Fit:** Selects the largest suitable free block.
4. **Next Fit:** Continues searching from the previous search position.
5. **Adaptive:** Selects an allocation strategy using free-list statistics and configurable thresholds.

## Workload Design

The simulator evaluates three operating points:

| Operating point | Requests | Heap size | Mean lifetime |
|---|---:|---:|---:|
| Small | 20,000 | 256 KiB | 600 ticks |
| Medium | 50,000 | 1 MiB | 2,400 ticks |
| Large | 100,000 | 4 MiB | 9,600 ticks |

The configured request sizes range from 16 bytes to 8 KiB. Workloads use variable request sizes and process lifetimes. Multiple seeds are used to examine variation across runs.

## Metrics

The simulator records allocation failure rate, fragmentation-related failures, out-of-memory failures, free-list nodes examined per allocation, allocation time, external fragmentation, free-block count, and memory utilization.

External fragmentation is calculated as:

`1 - (largest free block / total free memory)`

## Installation

Install Python 3.12 or a compatible version, then install the required packages:

```bash
pip install -r requirements.txt
```

## Running the Experiments

Run the threshold-tuning script if you want to tune the adaptive policy:

```bash
python tune_adaptive.py
```

After reviewing the selected thresholds and updating `config.json` if appropriate, run the simulator:

```bash
python alloc_sim.py --seeds 5 --out results
```

Generate summary tables and figures:

```bash
python analyze.py
```

For a separate tuned experiment, save the tuned configuration first and run:

```bash
python alloc_sim.py --seeds 5 --out results_tuned
python analyze.py --in results_tuned --out results_tuned/figs
```

Keep baseline and tuned outputs separate. Record the configuration and seeds used for each experiment so the results can be reproduced.

## Experimental Environment

- Operating system: Windows 11
- Python version: Python 3.12.3
- Processor: Intel64 Family 6 Model 154, Stepping 3
- Installed RAM: To be recorded
- Evaluation seeds: Record the exact seeds used for the submitted results.

## Results and Interpretation

The experiments compare allocation cost, allocation failures, and external fragmentation across the five strategies. The adaptive policy should be evaluated as a trade-off between these metrics rather than assumed to outperform every conventional strategy.

Refer to the committed CSV files and figures for the measured results. All conclusions should be based on the recorded experimental data.

## Repository

Source code, configuration, workload traces, and experimental results are available in this repository:

https://github.com/duagarvit50-spec/intelligent-memory-allocation
