import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import sys
from placer import Placer

# order: empty_core, T0, T1, T2, T3, pin, empty 
COLORS = ['#1a1a2e', '#4ade80', '#60a5fa', '#f97316', '#e879f9', '#fbbf24', '#0f0f0f']
CMAP = mcolors.ListedColormap(COLORS)


def build_grid_matrix(placer):
    ny, nx = placer.ny, placer.nx
    mat = np.zeros((ny, nx), dtype=int)
    for y in range(ny):
        for x in range(nx):
            cid = placer.grid[y][x]
            on_edge = (x == 0 or x == nx-1 or y == 0 or y == ny-1)
            if cid is None:
                mat[y][x] = 6 if on_edge else 0
            else:
                c = placer.components[cid]
                mat[y][x] = 5 if c.fixed else c.type + 1
    return mat


def plot_before_after(placer, cooling_rate=0.95):
    placer.initial_placement()
    init_hpwl = placer.compute_hpwl()
    mat_before = build_grid_matrix(placer)

    print(f"Initial HPWL: {init_hpwl:,}")
    print("Running SA:")
    best_cost, _ = placer.anneal(cooling_rate=cooling_rate) #discards history
    print(f"Final HPWL:   {best_cost:,}")

    mat_after = build_grid_matrix(placer)
    fig, axes = plt.subplots(1, 2, figsize=(20, 10), facecolor='#0f0f0f')

    for ax, mat, label, hpwl in [
        (axes[0], mat_before, 'Initial Placement', init_hpwl),
        (axes[1], mat_after,  'After SA',          best_cost),
    ]:
        #background and render matrix
        ax.set_facecolor('#0f0f0f')
        ax.imshow(mat, cmap=CMAP, vmin=0, vmax=6,
                  origin='upper', interpolation='nearest', aspect='equal')
        ax.set_title(f'{label}\nHPWL = {hpwl:,}', color='white', fontsize=13, pad=10)
        ax.tick_params(colors='#666')
        for sp in ax.spines.values():
            sp.set_edgecolor('#333')

    legend_items = [
        mpatches.Patch(color=COLORS[1], label='T0 (60%)'),
        mpatches.Patch(color=COLORS[2], label='T1 (25%)'),
        mpatches.Patch(color=COLORS[3], label='T2 (10%)'),
        mpatches.Patch(color=COLORS[4], label='T3 (5%)'),
        mpatches.Patch(color=COLORS[5], label='Fixed Pin'),
        mpatches.Patch(color=COLORS[0], label='Empty'),
    ]
    axes[1].legend(handles=legend_items, loc='upper right', fontsize=8,
                   framealpha=0.7, facecolor='#1a1a2e', labelcolor='white', edgecolor='#444')

    plt.suptitle('Structured ASIC SA Placer', color='white', fontsize=15, y=1.01)
    plt.tight_layout()
    plt.savefig('placement_comparison.png', dpi=150,
                bbox_inches='tight', facecolor=fig.get_facecolor())
    print("Saved: placement_comparison.png")
    plt.show()


class SnapshotCollector:
    def __init__(self, placer):
        self._placer = placer
        self._data   = []
        self._step   = 0

    def __call__(self, T, cost):
        self._step += 1
        mat = build_grid_matrix(self._placer).copy()
        self._data.append((self._step, T, cost, mat))

    def get_snapshots(self, n=6):
        total = len(self._data)
        if total == 0:
            return []
        if total <= n:
            return self._data
        idx = [int(round(i * (total - 1) / (n - 1))) for i in range(n)]
        return [self._data[i] for i in idx]


def show_progress_snapshots(snapshots, placer, save_path=None):
    if not snapshots:
        print("No snapshots.")
        return

    n    = len(snapshots)
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    ny, nx = placer.ny, placer.nx

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 6, rows * 5.5), facecolor='#0f0f0f')
    axes = np.array(axes).reshape(-1)

    for i, (step, T, cost, mat) in enumerate(snapshots):
        ax = axes[i]
        ax.set_facecolor('#0f0f0f')
        ax.imshow(mat, cmap=CMAP, vmin=0, vmax=6,
                  origin='upper', interpolation='nearest', aspect='equal')
        ax.add_patch(plt.Rectangle((-0.5, -0.5), nx, ny,
                                    lw=1, edgecolor='#fbbf24', facecolor='none', zorder=5))
        ax.tick_params(colors='#666', labelsize=6)
        for sp in ax.spines.values():
            sp.set_edgecolor('#333')

        label = 'Initial' if i == 0 else ('Final' if i == n - 1 else f'Step {step}')
        ax.set_title(f'{label}\nT={T:.2e}  HPWL={cost:,}', color='white', fontsize=9, pad=6)
        ax.set_xlabel('X', color='#aaa', fontsize=7)
        ax.set_ylabel('Y', color='#aaa', fontsize=7)

    for j in range(n, len(axes)):
        axes[j].set_visible(False)

    legend_items = [
        mpatches.Patch(color=COLORS[1], label='T0 (60%)'),
        mpatches.Patch(color=COLORS[2], label='T1 (25%)'),
        mpatches.Patch(color=COLORS[3], label='T2 (10%)'),
        mpatches.Patch(color=COLORS[4], label='T3 (5%)'),
        mpatches.Patch(color=COLORS[5], label='Fixed Pin'),
        mpatches.Patch(color=COLORS[0], label='Empty'),
    ]
    axes[n - 1].legend(handles=legend_items, loc='upper right', fontsize=8,
                       framealpha=0.7, facecolor='#1a1a2e', labelcolor='white', edgecolor='#444')

    plt.suptitle('SA Placement Progress', color='white', fontsize=13, fontweight='bold', y=1.01)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"Saved: {save_path}")
    plt.show()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python visualize")
        sys.exit(1)

    args = sys.argv[1:]
    netlist = args[0]
    compare = 'compare' in args

    frames = 6
    if 'frames' in args:
        i = args.index('frames')
        frames = int(args[i + 1])

    save_path = None
    if 'save' in args:
        i = args.index('save')
        save_path = args[i + 1]

    placer = Placer(netlist)

    if compare:
        plot_before_after(placer)
    else:
        placer.initial_placement()
        collector = SnapshotCollector(placer)
        best_cost, _ = placer.anneal(cooling_rate=0.95, on_step=collector)
        print(f"Final HPWL: {best_cost:,}")
        show_progress_snapshots(collector.get_snapshots(frames), placer, save_path=save_path)
