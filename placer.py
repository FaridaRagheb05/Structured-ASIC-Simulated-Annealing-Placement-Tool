from collections import defaultdict
import random

master_Tile = [
    [0, 1, 0, 2, 0],
    [1, 0, 1, 0, 1],
    [0, 2, 3, 0, 2],
    [1, 0, 1, 0, 0],
    [0, 0, 0, 0, 0],
]

def site_Type(x, y):
    return master_Tile[(y - 1) % 5][(x - 1) % 5]

# needed data structures

class Component:
    def __init__(self, ID, Type, X_Coord=None, Y_Coord=None, Fixed=False):
        self.id = ID
        self.type = Type  # int (0 to 3) for cells (T0-T3) and set to -1 for pins
        self.x = X_Coord
        self.y = Y_Coord
        self.fixed = Fixed  # True if pin but false if (movable) cell
  

class Placer:
    def __init__(self, netlist_path):
        self.components = {}
        self.nets = []  # list of lists of component ids
        self.ny = self.nx = 0

        # grid[y][x] -> component id or None
        self.grid = None

        # type -> list of (x,y) sites in core (precomputed and static)
        self.sites_by_type = defaultdict(list)

        # type -> set of (x,y) sites that are currently empty
        self.empty_by_type = defaultdict(set)
        self.cell_to_nets = defaultdict(list)
        self.movable_cells = [] 
        
        self._parse_Input(netlist_path)
        self._build_Grid()
        self._build_cell_to_nets()
        self.movable_cells = [c.id for c in self.components.values() if not c.fixed]


    def _parse_Input(self, input_File):
        with open(input_File) as f:
            # remove comments and empty lines
            lines = [l.split('#')[0].strip() for l in f]
            lines = [l for l in lines if l]

        index = 0

        # section 1:parse global header
        header = lines[index].split()
        index += 1
        NumCells, NumNets, self.ny, self.nx, NumFixedPins = (int(v) for v in header[:5])

        # section 2: parse component definitions (pins and cells)
        for _ in range(NumCells):
            line = lines[index].split()
            index += 1
            ID = int(line[0])

            if line[-1] == 'P':
                # Fixed pin definition: [ID] [X_Coord] [Y_Coord] P
                X_Coord = int(line[1])
                Y_Coord = int(line[2])

                # validate pin is on perimeter
                if not self._is_Valid_Pin_Coord(X_Coord, Y_Coord):
                    raise ValueError(f"Pin {ID} at ({X_Coord}, {Y_Coord}) not on perimeter")

                self.components[ID] = Component(ID, Type=-1, X_Coord=X_Coord, Y_Coord=Y_Coord, Fixed=True)

            else:
                # Movable cell definition: [ID] [Type]
                Type = int(line[1][1])  # "T0" -> 0, "T1" -> 1, ...

                if Type < 0 or Type > 3:
                    raise ValueError(f"Cell {ID} has invalid type {Type}")

                self.components[ID] = Component(ID, Type=Type, Fixed=False)

        # Section 3: parse net connectivity
        for _ in range(NumNets):
            line = lines[index].split()
            index += 1
            NumAttached = int(line[0])
            attached_IDs = [int(line[i]) for i in range(1, NumAttached + 1)]
            self.nets.append(attached_IDs)

        print(f"Parsed {NumCells} components, {NumNets} nets, grid {self.ny}x{self.nx}, {NumFixedPins} pins")

    def _is_Valid_Pin_Coord(self, x, y):
        """Check if pin coordinates are on perimeter (row 0, row ny-1, col 0, col nx-1)."""
        return (x == 0 or x == self.nx - 1 or y == 0 or y == self.ny - 1)

    def _build_Grid(self):
        """Build grid, place fixed pins, enumerate core sites by type."""
        self.grid = [[None] * self.nx for _ in range(self.ny)]

        # place fixed pins on grid
        for comp in self.components.values():
            if comp.fixed:
                self.grid[comp.y][comp.x] = comp.id

        # enumerate all core sites by type
        for y in range(1, self.ny - 1):
            for x in range(1, self.nx - 1):
                t = site_Type(x, y)
                self.sites_by_type[t].append((x, y))
                self.empty_by_type[t].add((x, y))

        counts = {t: len(v) for t, v in self.sites_by_type.items()}
        print(f"Grid: Core sites by type: {counts}")

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
            
            if len(cell_ids) > len(sites):
                raise RuntimeError(f"Not enough T{t} sites for {len(cell_ids)} cells")
            
            for cell_id, (x, y) in zip(cell_ids, sites):
                comp = self.components[cell_id]
                comp.x = x
                comp.y = y
                self.grid[y][x] = cell_id
                self.empty_by_type[t].discard((x, y))  # mark site as occupied

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

        self.apply_move(id_a, id_b, xa, ya, xb, yb)

        cost_after = sum(self._net_hpwl(ni) for ni in affected)

        self.apply_move(id_a, id_b, xb, yb, xa, ya)

        return cost_after - cost_before


    def generate_move(self):
        id_a = random.choice(self.movable_cells)
        comp_a = self.components[id_a]
        t = comp_a.type

        same_type_cells = [c.id for c in self.components.values()
                        if not c.fixed and c.type == t and c.id != id_a]
        empty_sites = list(self.empty_by_type[t])

        candidates = same_type_cells + empty_sites  
        if not candidates:
            return None  
        target = random.choice(candidates)

        if isinstance(target, tuple):
            xb, yb = target
            return (id_a, None, comp_a.x, comp_a.y, xb, yb)
        else:
            comp_b = self.components[target]
            return (id_a, target, comp_a.x, comp_a.y, comp_b.x, comp_b.y)


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



    def render(self):
        for y in range(self.ny):
            row = []
            for x in range(self.nx):
                cid = self.grid[y][x]
                if cid is None:
                    if (x == 0 or x == self.nx-1 or
                        y == 0 or y == self.ny-1):
                        row.append(' ')
                    else:
                        row.append('.')
                else:
                    comp = self.components[cid]
                    if comp.fixed:
                        row.append('P')
                    else:
                        row.append(str(comp.type))
            print(''.join(row))

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python placer_parsing.py <netlist_file>")
        sys.exit(1)

    placer = Placer(sys.argv[1])
    print(f"Components loaded: {len(placer.components)}")
    print(f"Nets loaded: {len(placer.nets)}")
    placer.initial_placement()
    placer.render()
