from game.tile import Tile
from game.unit import Unit, create_pinpoint
from typing import Dict, Tuple
import random

class HexMap:
    def __init__(self, size: int = 8):
        self.size = size
        self.tiles: Dict[Tuple[int,int], Tile] = {}
        self._generate_map()
        self._setup_starting_ownership()
        self._place_pinpoints()
        self._place_gold_mine()

    def _generate_map(self):
        for q in range(-self.size, self.size+1):
            r1 = max(-self.size, -q - self.size)
            r2 = min(self.size, -q + self.size)
            for r in range(r1, r2+1):
                self.tiles[(q,r)] = Tile(q, r, owner='ally')  # 초기 임시 owner

    def _setup_starting_ownership(self):
        # 맵 절반씩 아군/적 설정
        for (q,r), tile in self.tiles.items():
            if q < 0:
                tile.owner = 'ally'
            else:
                tile.owner = 'enemy'

        # 경계 타일 설정
        for (q,r), tile in self.tiles.items():
            for neighbor in self.neighbors(q,r):
                if neighbor.owner != tile.owner:
                    tile.boundary = True

    def _place_pinpoints(self):
        # 양 끝 중앙에 핀포인트 유닛 배치
        ally_q = min(q for q,r in self.tiles)
        enemy_q = max(q for q,r in self.tiles)
        ally_r = 0
        enemy_r = 0
        self.get_tile(ally_q, ally_r).place_unit(create_pinpoint('ally'))
        self.get_tile(enemy_q, enemy_r).place_unit(create_pinpoint('enemy'))

    def _place_gold_mine(self):
        # 아군 경계 안쪽 랜덤 타일에 금광
        candidates = [t for t in self.tiles.values() if t.owner=='ally' and not t.boundary]
        gold_tile = random.choice(candidates)
        gold_tile.terrain = 'gold'
        gold_tile.gold_cooldown = 0
        gold_tile.gold_amount = random.randint(50,2000)

    def get_tile(self, q,r):
        return self.tiles.get((q,r))

    def neighbors(self, q,r):
        directions = [(+1,0),(+1,-1),(0,-1),(-1,0),(-1,+1),(0,+1)]
        result = []
        for dq, dr in directions:
            neighbor = self.get_tile(q+dq, r+dr)
            if neighbor:
                result.append(neighbor)
        return result
