# Structured-ASIC-Simulated-Annealing-Placement-Tool

This project implements a structured ASIC placement tool using Simulated Annealing. The goal is to place movable cells on legal typed sites while minimizing total wire length, reported in the code as HPWL. For this project, TWL is the sum of HPWL across all nets.

The placer supports fixed perimeter pins, typed placement sites, legal same-type swaps, moves into empty compatible sites, and incremental wire length updates for faster annealing.

## Project Goal

The assignment asks for a placer that improves final placement quality while keeping runtime practical on every benchmark design. The largest benchmark is `design_5_extreme.txt`, and the optimized branches were tuned so the extreme case runs well under one minute.

## Repository Files

| File | Purpose |
|---|---|
| `placer.py` | Main placer implementation |
| `initial_placement.py` | Initial placement experiments and support code |
| `design_1_small.txt` | Small test case |
| `design_2_medium.txt` | Medium test case |
| `design_3_large.txt` | Large test case |
| `design_4_dense.txt` | Dense test case |
| `design_5_extreme.txt` | Worst-case benchmark |
| `output.txt`, `placement_output.txt`, `status_report.txt` | Generated output and notes |
| `history_*.csv`, `*.png` | Generated history and visualization files |

## Input Format

Each design file starts with:

```text
<num_components> <num_nets> <grid_rows> <grid_cols> <num_fixed_pins>
```

Then it lists movable cells and fixed pins:

```text
<cell_id> T<type>
<pin_id> <x> <y> P
```

Then it lists nets:

```text
<num_attached_components> <component_id_1> <component_id_2> ...
```

Pins are fixed on the grid perimeter. Movable cells must be placed on compatible typed sites.

## Grid and Site Types

The core grid uses a repeating 5 by 5 master tile:

```text
0 1 0 2 0
1 0 1 0 1
0 2 3 0 2
1 0 1 0 0
0 0 0 0 0
```

A cell of type `T0`, `T1`, `T2`, or `T3` can only be placed on a site with the matching number. The outer perimeter is reserved for fixed pins.

## Base Algorithm

The main algorithm is Simulated Annealing:

1. Parse cells, pins, nets, and grid size.
2. Build the placement grid and legal site lists by type.
3. Generate an initial legal placement.
4. Repeatedly try legal moves:
   - swap two movable cells of the same type
   - move a cell into an empty site of the same type
5. Compute the change in TWL using only affected nets.
6. Accept improving moves immediately.
7. Accept some worse moves using the SA probability rule.
8. Track and restore the best placement found.

The cost function is:

```text
TWL = sum over all nets ((max_x - min_x) + (max_y - min_y))
```

## Runtime Optimizations

The `optimization` branch improves runtime using:

- Incremental TWL delta calculation instead of recomputing every net after every move.
- A `cell_to_nets` map so each move only checks nets connected to the moved cells.
- Precomputed legal sites by cell type.
- Empty-site tracking by type.
- Reduced move counts for large designs.
- Early stopping when the annealer stops improving.
- A runtime guard so worst-case benchmarks stay under the required limit.

## Bonus Branches

Each bonus was kept in a separate branch so the approaches can be compared independently.

| Branch | Bonus Implemented | Description |
|---|---|---|
| `optimization` | Runtime optimization | Fast baseline using incremental TWL updates and early stopping |
| `optimized-adaptive-reheating` | SA variation | Raises temperature when acceptance drops too low, helping escape local minima |
| `optimized-range-limiting` | SA variation | Restricts swap distance as temperature drops so late-stage moves become more local |
| `optimized-force-directed-placement` | Alternative initial placement | Uses net connectivity as a spring-like guide before SA refinement |
| `optimized-heuristic-intelligence` | Greedy look-ahead | Samples candidate moves, scores their TWL delta, and prioritizes high-gain moves |

## Running the Placer

Run from the repository root:

```bash
python3 placer.py design_1_small.txt
```

Some optimized branches support suppressing the final grid printout:

```bash
python3 placer.py design_5_extreme.txt --no-render
```

To test a specific branch:

```bash
git checkout optimized-range-limiting
python3 placer.py design_5_extreme.txt --no-render
```

## Benchmark Designs

The project includes five benchmark cases:

| Design | Components | Nets | Notes |
|---|---:|---:|---|
| `design_1_small.txt` | 150 | 120 | Small sanity test |
| `design_2_medium.txt` | 300 | 250 | Medium test |
| `design_3_large.txt` | 500 | 450 | Large test |
| `design_4_dense.txt` | 800 | 750 | Dense netlist |
| `design_5_extreme.txt` | 1200 | 1100 | Worst-case benchmark |

## Latest Benchmark Summary

These results were measured without counting final grid rendering time. All tested placements were legal.

| Branch | Worst Runtime | Best Use |
|---|---:|---|
| `optimization` | 50.39s | Fast baseline, but one case is close to the limit |
| `optimized-adaptive-reheating` | 9.09s | Very fast SA variation |
| `optimized-force-directed-placement` | 7.07s | Fastest branch, guided initial placement |
| `optimized-range-limiting` | 15.18s | Best overall bonus branch from the tested set |
| `optimized-heuristic-intelligence` | 40.00s | Stronger TWL improvement using greedy look-ahead |

### Comparison Against `optimization`

| Design | `optimization` Final TWL | Adaptive Reheating | Force Directed | Range Limiting |
|---|---:|---:|---:|---:|
| `design_1_small.txt` | 2186 | 2203 | 2219 | 2185 |
| `design_2_medium.txt` | 3432 | 3609 | 3646 | 3530 |
| `design_3_large.txt` | 6048 | 6631 | 6738 | 6547 |
| `design_4_dense.txt` | 12379 | 12473 | 12422 | 12086 |
| `design_5_extreme.txt` | 21523 | 21359 | 21134 | 20903 |

Range limiting gave the best result on the extreme design among these three branches, while staying well under 30 seconds.

### Heuristic Intelligence Results

The heuristic branch uses greedy look-ahead move selection. It evaluates a small set of legal moves before choosing one, then prioritizes the move with the best TWL delta.

| Design | Final TWL | Runtime | Legal |
|---|---:|---:|---|
| `design_1_small.txt` | 2148 | 37.87s | Yes |
| `design_2_medium.txt` | 3357 | 40.00s | Yes |
| `design_3_large.txt` | 6261 | 40.00s | Yes |
| `design_4_dense.txt` | 11105 | 26.61s | Yes |
| `design_5_extreme.txt` | 19141 | 24.93s | Yes |

This branch gives the strongest extreme-case TWL result from the tested branches.

## Notes on Quality and Runtime

The branches make different tradeoffs:

- `optimized-force-directed-placement` is the fastest, but it does not always beat the optimized SA baseline in final TWL.
- `optimized-adaptive-reheating` is fast and simple, but its quality gains are case-dependent.
- `optimized-range-limiting` is a good submission candidate because it improves the extreme case and several other cases while staying fast.
- `optimized-heuristic-intelligence` gives the best extreme-case TWL, but it spends more time evaluating candidate moves.

## Requirements

The code uses Python 3 and the standard library:

- `collections`
- `random`
- `math`
- `time`
- `sys`

No external Python packages are required for the core placer.

