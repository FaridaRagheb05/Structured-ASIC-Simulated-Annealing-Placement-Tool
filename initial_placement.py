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