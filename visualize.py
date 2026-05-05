import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import random
import sys
from placer import Placer

# 0=empty core, 1=T0, 2=T1, 3=T2, 4=T3, 5=pin, 6=empty perimeter
COLORS = {
    0: '#1a1a2e',   # empty core - dark navy
    1: '#4ade80',   # T0 - green
    2: '#60a5fa',   # T1 - blue
    3: '#f97316',   # T2 - orange
    4: '#e879f9',   # T3 - purple
    5: '#fbbf24',   # pin - gold
    6: '#0f0f0f',   # empty perimeter - near black
}

CMAP = mcolors.ListedColormap([COLORS[i] for i in range(7)])


def build_grid_matrix(placer):
    ny, nx = placer.ny, placer.nx
    matrix = np.zeros((ny, nx), dtype=int)

    for y in range(ny):
        for x in range(nx):
            cid = placer.grid[y][x]
            is_perimeter = (x == 0 or x == nx - 1 or y == 0 or y == ny - 1)
            if cid is None:
                matrix[y][x] = 6 if is_perimeter else 0
            else:
                comp = placer.components[cid]
                if comp.fixed:
                    matrix[y][x] = 5
                else:
                    matrix[y][x] = comp.type + 1  # T0->1, T1->2, T2->3, T3->4

    return matrix


def draw_net_sample(placer, ax, max_nets=40, alpha=0.25):
    nets = placer.nets
    sample = random.sample(nets, min(max_nets, len(nets)))
    for net in sample:
        xs = [placer.components[i].x for i in net]
        ys = [placer.components[i].y for i in net]
        ax.plot(xs, ys, color='white', linewidth=0.5, alpha=alpha, zorder=3)


def plot_placement(placer, title='SA Placement Heatmap', show_nets=True, save_path=None):
    matrix = build_grid_matrix(placer)

    fig, ax = plt.subplots(figsize=(10, 10), facecolor='#0f0f0f')
    ax.set_facecolor('#0f0f0f')

    ax.imshow(
        matrix,
        cmap=CMAP,
        vmin=0, vmax=6,
        origin='upper',
        interpolation='nearest',
        aspect='equal',
    )

    if show_nets:
        draw_net_sample(placer, ax)

    # perimeter border
    ny, nx = placer.ny, placer.nx
    rect = plt.Rectangle((-0.5, -0.5), nx, ny,
                          linewidth=1.5, edgecolor='#fbbf24',
                          facecolor='none', zorder=5)
    ax.add_patch(rect)

    legend_items = [
        mpatches.Patch(color=COLORS[1], label='T0 (60%)'),
        mpatches.Patch(color=COLORS[2], label='T1 (25%)'),
        mpatches.Patch(color=COLORS[3], label='T2 (10%)'),
        mpatches.Patch(color=COLORS[4], label='T3 (5%)'),
        mpatches.Patch(color=COLORS[5], label='Fixed Pin'),
        mpatches.Patch(color=COLORS[0], label='Empty Site'),
    ]
    ax.legend(
        handles=legend_items,
        loc='upper right',
        fontsize=9,
        framealpha=0.7,
        facecolor='#1a1a2e',
        labelcolor='white',
        edgecolor='#444',
    )

    hpwl = placer.compute_hpwl()
    ax.set_title(f'{title}\nHPWL = {hpwl:,}   |   Grid: {ny}×{nx}',
                 color='white', fontsize=13, pad=12)
    ax.set_xlabel('X (column)', color='#aaa', fontsize=9)
    ax.set_ylabel('Y (row)', color='#aaa', fontsize=9)
    ax.tick_params(colors='#666')
    for spine in ax.spines.values():
        spine.set_edgecolor('#333')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"Saved to {save_path}")
    else:
        plt.show()


def plot_before_after(placer, cooling_rate=0.95):
    placer.initial_placement()
    initial_hpwl = placer.compute_hpwl()
    matrix_before = build_grid_matrix(placer)

    print(f"Initial HPWL: {initial_hpwl:,}")
    print("Running SA annealing...")
    best_cost, _ = placer.anneal(cooling_rate=cooling_rate)
    print(f"Final HPWL:   {best_cost:,}")

    matrix_after = build_grid_matrix(placer)

    fig, axes = plt.subplots(1, 2, figsize=(20, 10), facecolor='#0f0f0f')

    for ax, matrix, label, hpwl in [
        (axes[0], matrix_before, 'Initial Placement', initial_hpwl),
        (axes[1], matrix_after,  'After SA Annealing', best_cost),
    ]:
        ax.set_facecolor('#0f0f0f')
        ax.imshow(matrix, cmap=CMAP, vmin=0, vmax=6,
                  origin='upper', interpolation='nearest', aspect='equal')
        ax.set_title(f'{label}\nHPWL = {hpwl:,}',
                     color='white', fontsize=13, pad=10)
        ax.tick_params(colors='#666')
        for spine in ax.spines.values():
            spine.set_edgecolor('#333')

    legend_items = [
        mpatches.Patch(color=COLORS[1], label='T0'),
        mpatches.Patch(color=COLORS[2], label='T1'),
        mpatches.Patch(color=COLORS[3], label='T2'),
        mpatches.Patch(color=COLORS[4], label='T3'),
        mpatches.Patch(color=COLORS[5], label='Pin'),
        mpatches.Patch(color=COLORS[0], label='Empty'),
    ]
    axes[1].legend(handles=legend_items, loc='upper right', fontsize=9,
                   framealpha=0.7, facecolor='#1a1a2e',
                   labelcolor='white', edgecolor='#444')

    plt.suptitle('Structured ASIC SA Placer', color='white', fontsize=15, y=1.01)
    plt.tight_layout()
    plt.savefig('placement_comparison.png', dpi=150,
                bbox_inches='tight', facecolor=fig.get_facecolor())
    print("Saved to placement_comparison.png")
    plt.show()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python visualize.py <netlist_file> [--compare]")
        sys.exit(1)

    netlist = sys.argv[1]
    compare = '--compare' in sys.argv

    placer = Placer(netlist)

    if compare:
        plot_before_after(placer)
    else:
        placer.initial_placement()
        placer.anneal(cooling_rate=0.95)
        plot_placement(placer, save_path='placement.png')
