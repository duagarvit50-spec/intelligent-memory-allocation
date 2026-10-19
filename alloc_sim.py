"""
Dynamic-partition allocator simulator: First/Best/Worst/Next Fit + Adaptive.
Usage:  python alloc_sim.py --seeds 5 --out results
Outputs: results/runs.csv (one row per strategy x operating point x seed)
         results/frag_timeline.csv (sampled fragmentation over time)
         results/trace_<point>_<seed>.csv (the exact trace replayed to every strategy)
"""
import argparse, bisect, csv, heapq, math, os, random, time

# ---------------- configuration ----------------
# Three independent operating points: (name, n_requests, heap_bytes, mean_lifetime_ticks)
POINTS = [
    ("small",  20_000,    256 * 1024,  600),
    ("medium", 50_000,  1 * 1024 * 1024, 2400),
    ("large", 100_000,  4 * 1024 * 1024, 9600),
]
MEAN_SIZE = 256            # bytes, lognormal median-ish
SIZE_SIGMA = 1.0           # lognormal spread
MIN_SIZE, MAX_SIZE = 16, 8192
SAMPLE_EVERY = 100         # ticks between fragmentation samples
ADAPT = dict(small_n=8, frag_hi=0.5, big_frac=0.25, refresh=50)
STRATEGIES = ["first", "best", "worst", "next", "adaptive"]

# Optional override from config.json (kept next to this file)
_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
if os.path.exists(_cfg_path):
    import json
    _c = json.load(open(_cfg_path))
    POINTS = [tuple(p) for p in _c.get("points", POINTS)]
    MEAN_SIZE = _c.get("mean_size", MEAN_SIZE)
    SIZE_SIGMA = _c.get("size_sigma", SIZE_SIGMA)
    MIN_SIZE = _c.get("min_size", MIN_SIZE)
    MAX_SIZE = _c.get("max_size", MAX_SIZE)
    SAMPLE_EVERY = _c.get("sample_every", SAMPLE_EVERY)
    ADAPT.update(_c.get("adaptive", {}))


# ---------------- workload generator ----------------
def gen_trace(n, mean_life, seed):
    """Returns list of events (tick, op, id, size). One request per tick,
    lifetimes exponential => variable block sizes and process lifetimes."""
    rng = random.Random(seed)
    mu = math.log(MEAN_SIZE)
    events, pending = [], []
    for t in range(n):
        while pending and pending[0][0] <= t:
            _, bid = heapq.heappop(pending)
            events.append((t, "F", bid, 0))
        size = int(min(MAX_SIZE, max(MIN_SIZE, rng.lognormvariate(mu, SIZE_SIGMA))))
        life = max(1, int(rng.expovariate(1.0 / mean_life)))
        events.append((t, "A", t, size))
        heapq.heappush(pending, (t + life, t))
    return events


# ---------------- allocator ----------------
class Heap:
    def __init__(self, size, strategy):
        self.size = size
        self.starts, self.sizes = [0], [size]   # free list sorted by address
        self.total_free = size
        self.strategy = strategy
        self.rover = 0
        self.steps = 0                           # free-list nodes examined
        self.n_alloc = 0
        self.cached_largest = size
        self.since_refresh = 10**9
        self.choice_count = {"first": 0, "best": 0, "next": 0}

    # --- fit searches: return index of chosen free block or -1 ---
    def _first(self, req):
        s = self.sizes
        for i in range(len(s)):
            self.steps += 1
            if s[i] >= req:
                return i
        return -1

    def _next(self, req):
        s, n = self.sizes, len(self.sizes)
        if n == 0:
            return -1
        start = self.rover % n
        for k in range(n):
            i = (start + k) % n
            self.steps += 1
            if s[i] >= req:
                return i
        return -1

    def _best(self, req):
        s, best, bi = self.sizes, None, -1
        for i in range(len(s)):
            self.steps += 1
            if s[i] >= req and (best is None or s[i] < best):
                best, bi = s[i], i
                if best == req:
                    break
        return bi

    def _worst(self, req):
        s, big, bi = self.sizes, -1, -1
        for i in range(len(s)):
            self.steps += 1
            if s[i] >= req and s[i] > big:
                big, bi = s[i], i
        return bi

    # --- adaptive selector based on current free-block statistics ---
    def _adaptive(self, req):
        c = ADAPT
        n = len(self.sizes)
        if self.since_refresh >= c["refresh"]:       # refresh costs a scan; counted
            self.cached_largest = max(self.sizes) if n else 0
            self.steps += n
            self.since_refresh = 0
        self.since_refresh += 1
        frag = 1.0 - (self.cached_largest / self.total_free) if self.total_free else 1.0
        if n <= c["small_n"]:
            pick = "first"
        elif frag >= c["frag_hi"] or req >= c["big_frac"] * self.cached_largest:
            pick = "best"
        else:
            pick = "next"
        self.choice_count[pick] += 1
        return getattr(self, "_" + pick)(req)

    def alloc(self, req):
        """Returns address, or -1 on failure. Sets self.last_fail_kind."""
        i = getattr(self, "_" + self.strategy)(req)
        if i < 0:
            self.last_fail_kind = "frag" if self.total_free >= req else "oom"
            return -1
        addr = self.starts[i]
        if self.sizes[i] == req:
            del self.starts[i]; del self.sizes[i]
        else:
            self.starts[i] += req; self.sizes[i] -= req
        self.total_free -= req
        self.rover = i
        self.n_alloc += 1
        return addr

    def free(self, addr, size):
        i = bisect.bisect_left(self.starts, addr)
        self.total_free += size
        merge_prev = i > 0 and self.starts[i-1] + self.sizes[i-1] == addr
        merge_next = i < len(self.starts) and addr + size == self.starts[i]
        if merge_prev and merge_next:
            self.sizes[i-1] += size + self.sizes[i]
            del self.starts[i]; del self.sizes[i]
        elif merge_prev:
            self.sizes[i-1] += size
        elif merge_next:
            self.starts[i] = addr; self.sizes[i] += size
        else:
            self.starts.insert(i, addr); self.sizes.insert(i, size)

    def ext_frag(self):
        return 1.0 - max(self.sizes) / self.total_free if self.sizes and self.total_free else 0.0


# ---------------- experiment driver ----------------
def run(strategy, trace, heap_size, pname, seed, timeline_writer):
    h = Heap(heap_size, strategy)
    live = {}
    fails = {"frag": 0, "oom": 0}
    ns_total = 0
    frag_s, nfree_s, util_s = [], [], []
    peak_free_blocks = 1
    for tick, op, bid, size in trace:
        if op == "A":
            t0 = time.perf_counter_ns()
            addr = h.alloc(size)
            ns_total += time.perf_counter_ns() - t0
            if addr < 0:
                fails[h.last_fail_kind] += 1
            else:
                live[bid] = (addr, size)
            if tick % SAMPLE_EVERY == 0:
                f = h.ext_frag()
                frag_s.append(f); nfree_s.append(len(h.sizes))
                util_s.append(1 - h.total_free / heap_size)
                peak_free_blocks = max(peak_free_blocks, len(h.sizes))
                timeline_writer.writerow([pname, seed, strategy, tick, f, len(h.sizes)])
        else:
            if bid in live:
                a, s = live.pop(bid)
                h.free(a, s)
    n_req = sum(1 for e in trace if e[1] == "A")
    m = lambda x: sum(x) / len(x) if x else 0
    return dict(point=pname, seed=seed, strategy=strategy, n_requests=n_req,
                heap_bytes=heap_size, fail_total=fails["frag"] + fails["oom"],
                fail_due_to_frag=fails["frag"], fail_oom=fails["oom"],
                fail_rate=(fails["frag"] + fails["oom"]) / n_req,
                steps_per_alloc=h.steps / n_req, ns_per_alloc=ns_total / n_req,
                mean_ext_frag=m(frag_s), mean_free_blocks=m(nfree_s),
                peak_free_blocks=peak_free_blocks, mean_util=m(util_s),
                adapt_first=h.choice_count["first"], adapt_best=h.choice_count["best"],
                adapt_next=h.choice_count["next"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true", help="only the small point (smoke test)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    points = POINTS[:1] if a.quick else POINTS
    rows = []
    with open(os.path.join(a.out, "frag_timeline.csv"), "w", newline="") as tf:
        tw = csv.writer(tf)
        tw.writerow(["point", "seed", "strategy", "tick", "ext_frag", "free_blocks"])
        for pname, n, heap_size, life in points:
            for seed in range(a.seeds):
                trace = gen_trace(n, life, seed)
                with open(os.path.join(a.out, f"trace_{pname}_{seed}.csv"), "w", newline="") as f:
                    w = csv.writer(f); w.writerow(["tick", "op", "id", "size"]); w.writerows(trace)
                for strat in STRATEGIES:
                    rows.append(run(strat, trace, heap_size, pname, seed, tw))
                    print(pname, seed, strat, f"fail={rows[-1]['fail_rate']:.4f}",
                          f"frag={rows[-1]['mean_ext_frag']:.3f}", f"steps={rows[-1]['steps_per_alloc']:.1f}")
    with open(os.path.join(a.out, "runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
