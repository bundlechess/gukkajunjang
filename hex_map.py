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
        self._place_gold_mine()

    def _generate_map(self):
        for q in range(-self.size, self.size + 1):
            r1 = max(-self.size, -q - self.size)
            r2 = min(self.size, -q + self.size)
            for r in range(r1, r2 + 1):
                self.tiles[(q, r)] = Tile(q, r, owner='ally')  # 임시로 ally

    def _setup_starting_ownership(self):
        # 맵을 q<0 아군 / q>=0 적군으로 분할
        for (q, r), tile in self.tiles.items():
            tile.owner = 'ally' if q < 0 else 'enemy'

        # 경계 타일 표시
        for (q, r), tile in self.tiles.items():
            for neighbor in self.neighbors(q, r):
                if neighbor.owner != tile.owner:
                    tile.boundary = True
                    break

    def _place_pinpoints(self):
        # 좌측 끝 중앙 / 우측 끝 중앙
        ally_q = min(q for q, _ in self.tiles.keys())
        enemy_q = max(q for q, _ in self.tiles.keys())
        ally_r = 0
        enemy_r = 0
        self.get_tile(ally_q, ally_r).place_unit(create_pinpoint('ally'))
        self.get_tile(enemy_q, enemy_r).place_unit(create_pinpoint('enemy'))

    def _place_gold_mine(self):
        # 아군 경계 '안쪽' 랜덤 금광 1개
        candidates = [t for t in self.tiles.values() if t.owner == 'ally' and not t.boundary]
        if not candidates:
            candidates = [t for t in self.tiles.values() if t.owner == 'ally']
        gold_tile = random.choice(candidates)
        gold_tile.terrain = 'gold'
        gold_tile.gold_cooldown = 0
        gold_tile.gold_amount = random.randint(50, 2000)

    def get_tile(self, q, r):
        return self.tiles.get((q, r))

    def neighbors(self, q, r):
        directions = [(+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)]
        result = []
        for dq, dr in directions:
            nb = self.get_tile(q + dq, r + dr)
            if nb:
                result.append(nb)
        return result
