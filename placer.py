from collections import defaultdict
import random
import math
import time
import sys

master_Tile = [
    [0, 1, 0, 2, 0],
    [1, 0, 1, 0, 1],
    [0, 2, 3, 0, 2],
    [1, 0, 1, 0, 0],
    [0, 0, 0, 0, 0],
]

def site_Type(x, y):
    return master_Tile[(y - 1) % 5][(x - 1) % 5]


class Component:
    __slots__ = ('id', 'type', 'x', 'y', 'fixed')
    def __init__(self, ID, Type, X_Coord=None, Y_Coord=None, Fixed=False):
        self.id = ID
        self.type = Type
        self.x = X_Coord
        self.y = Y_Coord
        self.fixed = Fixed


class Placer:
    def __init__(self, netlist_path):
        self.components = {}
        self.nets = []
        self.ny = self.nx = 0
        self.grid = None
        self.sites_by_type = defaultdict(list)
        self.empty_by_type = defaultdict(set)
        self.cell_to_nets = defaultdict(list)
        self.movable_cells = []
        self.cells_by_type = defaultdict(list)

        self._parse_Input(netlist_path)
        self._build_Grid()
        self._build_cell_to_nets()
        self.movable_cells = [c.id for c in self.components.values() if not c.fixed]
        for cid in self.movable_cells:
            self.cells_by_type[self.components[cid].type].append(cid)


    def _parse_Input(self, input_File):
        with open(input_File) as f:
            lines = [l.split('#')[0].strip() for l in f]
            lines = [l for l in lines if l]

        index = 0
        header = lines[index].split()
        index += 1
        NumCells, NumNets, self.ny, self.nx, NumFixedPins = (int(v) for v in header[:5])

        for _ in range(NumCells):
            line = lines[index].split()
            index += 1
            ID = int(line[0])

            if line[-1] == 'P':
                X_Coord = int(line[1])
                Y_Coord = int(line[2])
                self.components[ID] = Component(ID, Type=-1, X_Coord=X_Coord, Y_Coord=Y_Coord, Fixed=True)
            else:
                Type = int(line[1][1])
                self.components[ID] = Component(ID, Type=Type, Fixed=False)

        for _ in range(NumNets):
            line = lines[index].split()
            index += 1
            NumAttached = int(line[0])
            attached_IDs = [int(line[i]) for i in range(1, NumAttached + 1)]
            self.nets.append(attached_IDs)

        print(f"Parsed {NumCells} cells, {NumNets} nets, grid {self.ny}x{self.nx}")

    def _build_Grid(self):
        self.grid = [[None] * self.nx for _ in range(self.ny)]

        for comp in self.components.values():
            if comp.fixed:
                self.grid[comp.y][comp.x] = comp.id

        for y in range(1, self.ny - 1):
            for x in range(1, self.nx - 1):
                t = site_Type(x, y)
                self.sites_by_type[t].append((x, y))
                self.empty_by_type[t].add((x, y))

    def _build_cell_to_nets(self):
        for net_idx, net in enumerate(self.nets):
            for cell_id in net:
                self.cell_to_nets[cell_id].append(net_idx)

    def initial_placement(self, seed=42):
        random.seed(seed)

        cells_by_type = defaultdict(list)
        for comp in self.components.values():
            if not comp.fixed:
                cells_by_type[comp.type].append(comp.id)

        for t, cell_ids in cells_by_type.items():
            sites = list(self.sites_by_type[t])
            random.shuffle(sites)

            for cell_id, (x, y) in zip(cell_ids, sites):
                comp = self.components[cell_id]
                comp.x = x
                comp.y = y
                self.grid[y][x] = cell_id
                self.empty_by_type[t].discard((x, y))

    def compute_hpwl(self):
        total = 0
        for net in self.nets:
            xs = [self.components[i].x for i in net]
            ys = [self.components[i].y for i in net]
            total += (max(xs) - min(xs)) + (max(ys) - min(ys))
        return total

    def _net_hpwl(self, net_idx):
        net = self.nets[net_idx]
        xs = [self.components[i].x for i in net]
        ys = [self.components[i].y for i in net]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    def hpwl_delta(self, id_a, id_b, xa, ya, xb, yb):
        affected = set(self.cell_to_nets[id_a])
        if id_b is not None:
            affected |= set(self.cell_to_nets[id_b])

        cost_before = sum(self._net_hpwl(ni) for ni in affected)

        self.components[id_a].x = xb
        self.components[id_a].y = yb
        if id_b is not None:
            self.components[id_b].x = xa
            self.components[id_b].y = ya

        cost_after = sum(self._net_hpwl(ni) for ni in affected)

        self.components[id_a].x = xa
        self.components[id_a].y = ya
        if id_b is not None:
            self.components[id_b].x = xb
            self.components[id_b].y = yb

        return cost_after - cost_before

    def anneal(self, cooling_rate=0.95, on_step=None, max_seconds=45):
        start_time = time.time()
        initial_cost = self.compute_hpwl()
        num_nets = len(self.nets)
        num_cells = len(self.movable_cells)

        T = 500 * initial_cost
        T_final = (1e-4 * initial_cost) / num_nets

        if num_cells > 500:
            moves_per_T = max(10 * num_cells // (num_cells // 100), 100)
        else:
            moves_per_T = max(100, min(1000, 10 * num_cells))

        current_cost = initial_cost
        best_cost = current_cost
        best_pos = {
            cid: (self.components[cid].x, self.components[cid].y)
            for cid in self.movable_cells
        }

        history = []
        no_improve_count = 0
        max_no_improve = 20 + (5 if num_cells < 500 else 0)

        reheats_done = 0
        max_reheats = 5
        reheat_factor = 4.0

        iteration = 0

        while T > T_final:
            if time.time() - start_time >= max_seconds:
                break

            cost_before = current_cost
            accepted = 0

            for _ in range(moves_per_T):
                if time.time() - start_time >= max_seconds:
                    break

                move = self._gen_move_fast()
                if move is None:
                    continue

                id_a, id_b, xa, ya, xb, yb = move
                delta = self.hpwl_delta(id_a, id_b, xa, ya, xb, yb)

                if delta <= 0 or random.random() < math.exp(-delta / T):
                    self.apply_move(id_a, id_b, xa, ya, xb, yb)
                    current_cost += delta
                    accepted += 1

                    if current_cost < best_cost:
                        best_cost = current_cost
                        no_improve_count = 0
                        best_pos = {
                            cid: (self.components[cid].x, self.components[cid].y)
                            for cid in self.movable_cells
                        }

            T *= cooling_rate
            iteration += 1
            history.append((T, current_cost))

            if on_step is not None:
                on_step(T, current_cost)

            acceptance_rate = accepted / moves_per_T
            if acceptance_rate < 0.10 and reheats_done < max_reheats:
                T = min(T * reheat_factor, 500 * initial_cost * 0.1)
                reheats_done += 1

            if current_cost >= cost_before - 1e-6:
                no_improve_count += 1
            else:
                no_improve_count = 0

            if no_improve_count >= max_no_improve:
                break

        for cid, (x, y) in best_pos.items():
            self.components[cid].x = x
            self.components[cid].y = y

        self._rebuild_grid()

        return best_cost, history

    def _gen_move_fast(self):
        id_a = random.choice(self.movable_cells)
        comp_a = self.components[id_a]
        t = comp_a.type
        same_type_cells = self.cells_by_type[t]
        empty_sites = self.empty_by_type[t]

        candidates = len(same_type_cells) - 1 + len(empty_sites)
        if candidates <= 0:
            return None

        if same_type_cells and (not empty_sites or random.random() < 0.5):
            target = random.choice(same_type_cells)
            if target == id_a and len(same_type_cells) > 1:
                target = random.choice([c for c in same_type_cells if c != id_a])
            if target == id_a:
                return None
            comp_b = self.components[target]
            return (id_a, target, comp_a.x, comp_a.y, comp_b.x, comp_b.y)

        xb, yb = random.choice(tuple(empty_sites))
        return (id_a, None, comp_a.x, comp_a.y, xb, yb)

    def apply_move(self, id_a, id_b, xa, ya, xb, yb):
        t = self.components[id_a].type

        self.grid[ya][xa] = id_b
        self.grid[yb][xb] = id_a

        self.components[id_a].x = xb
        self.components[id_a].y = yb

        if id_b is not None:
            self.components[id_b].x = xa
            self.components[id_b].y = ya
        else:
            self.empty_by_type[t].add((xa, ya))
            self.empty_by_type[t].discard((xb, yb))

    def _rebuild_grid(self):
        self.grid = [[None] * self.nx for _ in range(self.ny)]
        for comp in self.components.values():
            if comp.x is not None:
                self.grid[comp.y][comp.x] = comp.id

    def refine_2opt(self, max_time=3):
        start_t = time.time()
        improved = True

        while improved and time.time() - start_t < max_time:
            improved = False

            for i_idx in range(len(self.movable_cells)):
                if time.time() - start_t > max_time:
                    break
                if improved:
                    break

                i = self.movable_cells[i_idx]
                comp_i = self.components[i]

                for j in self.movable_cells[i_idx + 1:]:
                    comp_j = self.components[j]
                    if comp_i.type != comp_j.type:
                        continue

                    delta = self.hpwl_delta(i, j, comp_i.x, comp_i.y, comp_j.x, comp_j.y)

                    if delta < -0.5:
                        self.apply_move(i, j, comp_i.x, comp_i.y, comp_j.x, comp_j.y)
                        improved = True
                        break

    def render_grid(self):
        for y in range(self.ny):
            row = []
            for x in range(self.nx):
                cid = self.grid[y][x]
                if cid is None:
                    row.append(' ' if (x == 0 or x == self.nx-1 or y == 0 or y == self.ny-1) else '.')
                else:
                    row.append('P' if self.components[cid].fixed else str(self.components[cid].type))
            print(''.join(row))


def main():
    if len(sys.argv) < 2:
        print("Usage: python placer.")
        sys.exit(1)

    netlist_file = sys.argv[1]
    use_2opt = '2opt' in sys.argv
    no_render = 'norender' in sys.argv
    show = 'show' in sys.argv

    cr = 0.95
    if 'cr' in sys.argv:
        i = sys.argv.index('cr')
        cr = float(sys.argv[i + 1])

    start = time.time()

    placer = Placer(netlist_file)
    placer.initial_placement()
    initial_cost = placer.compute_hpwl()

    collector = None
    if show:
        from visualize import SnapshotCollector
        collector = SnapshotCollector(placer)

    final_cost, history = placer.anneal(cooling_rate=cr, on_step=collector)

    if use_2opt:
        placer.refine_2opt(max_time=3)
        final_cost = placer.compute_hpwl()

    elapsed = time.time() - start
    improvement = 100 * (initial_cost - final_cost) / initial_cost

    print(f"Init: {initial_cost:.0f}  Final: {final_cost:.0f}  Improve: {improvement:.1f}%  Time: {elapsed:.2f}s")
    print()

    if not no_render:
        placer.render_grid()

    if show:
        from visualize import show_progress_snapshots
        show_progress_snapshots(collector.get_snapshots(6), placer)


if __name__ == '__main__':
    main()
