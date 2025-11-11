import random
from typing import Dict, Tuple
from game.tile import Tile
from game.unit import create_pinpoint

class HexMap:
    def __init__(self, size: int = 6):
        self.size = size
        self.tiles: Dict[Tuple[int, int], Tile] = {}
        self._generate_map()
        self._setup_starting_ownership()
        self._place_pinpoints()
        self._place_gold_mines()

    def _generate_map(self):
        for q in range(-self.size, self.size + 1):
            r1 = max(-self.size, -q - self.size)
            r2 = min(self.size, -q + self.size)
            for r in range(r1, r2 + 1):
                self.tiles[(q, r)] = Tile(q, r, owner='ally')

    def _setup_starting_ownership(self):
        for (q, r), tile in self.tiles.items():
            tile.owner = 'ally' if q < 0 else 'enemy'
        for (q, r), tile in self.tiles.items():
            for neighbor in self.neighbors(q, r):
                if neighbor.owner != tile.owner:
                    tile.boundary = True
                    break

    def _place_pinpoints(self):
        ally_q = min(q for q, _ in self.tiles.keys())
        enemy_q = max(q for q, _ in self.tiles.keys())
        self.get_tile(ally_q, 0).place_unit(create_pinpoint('ally'))
        self.get_tile(enemy_q, 0).place_unit(create_pinpoint('enemy'))

    def _place_gold_mines(self):
        """아군/적군 각각 1개씩 금광"""
        ally_candidates = [t for t in self.tiles.values() if t.owner == 'ally' and not t.boundary]
        enemy_candidates = [t for t in self.tiles.values() if t.owner == 'enemy' and not t.boundary]
        if not ally_candidates: ally_candidates = [t for t in self.tiles.values() if t.owner == 'ally']
        if not enemy_candidates: enemy_candidates = [t for t in self.tiles.values() if t.owner == 'enemy']

        a_tile = random.choice(ally_candidates)
        e_tile = random.choice(enemy_candidates)
        for t in [a_tile, e_tile]:
            t.terrain = 'gold'
            t.gold_cooldown = 0
            t.gold_amount = random.randint(50, 2000)
            t.gold_timer = 0.0

    def get_tile(self, q, r):
        return self.tiles.get((q, r))

    def neighbors(self, q, r):
        dirs = [(+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)]
        res = []
        for dq, dr in dirs:
            nb = self.get_tile(q + dq, r + dr)
            if nb:
                res.append(nb)
        return res
