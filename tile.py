from dataclasses import dataclass
from typing import Optional
from game.unit import Unit

@dataclass
class Tile:
    q: int
    r: int
    owner: str                  # 'ally' / 'enemy'
    terrain: str = "land"       # 'land' / 'gold'
    unit: Optional[Unit] = None
    blocked: bool = False       # 핀포인트 주변 설치 제한 등
    boundary: bool = False      # 경계 타일 여부
    gold_cooldown: int = 0      # 금광 쿨다운(초)
    gold_amount: int = 0        # 다음 채굴 금액(50~2000)

    # (선택) dict/set 키로 쓸 때 안전하게
    def __hash__(self) -> int:
        return hash((self.q, self.r))

    def __eq__(self, other) -> bool:
        return isinstance(other, Tile) and self.q == other.q and self.r == other.r

    def is_empty(self) -> bool:
        return self.unit is None

    def place_unit(self, unit: Unit):
        if not self.is_empty():
            raise ValueError(f"Tile({self.q},{self.r}) is not available for placement.")
        self.unit = unit

    def remove_unit(self) -> Unit:
        if self.unit is None:
            raise ValueError("No unit to remove.")
        removed = self.unit
        self.unit = None
        return removed
