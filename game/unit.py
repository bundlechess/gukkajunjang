from dataclasses import dataclass

@dataclass
class Unit:
    name: str
    movable: bool
    health: int
    attack: int
    owner: str  # 'ally' / 'enemy'
    is_pinpoint: bool = False
    is_setpoint: bool = False
    is_medical: bool = False
    is_maintenance: bool = False

    def take_damage(self, amount: int):
        self.health -= amount
        if self.health < 0:
            self.health = 0

    def is_alive(self):
        return self.health > 0

# === 유닛 생성 함수 ===
def create_pinpoint(owner: str) -> Unit:
    return Unit("Pinpoint", movable=False, health=100, attack=0, owner=owner, is_pinpoint=True)

def create_setpoint(owner: str) -> Unit:
    return Unit("Setpoint", movable=False, health=60, attack=5, owner=owner, is_setpoint=True)

def create_soldier(owner: str) -> Unit:
    return Unit("Soldier", movable=True, health=20, attack=2, owner=owner)

def create_medical(owner: str) -> Unit:
    return Unit("Medical", movable=False, health=40, attack=0, owner=owner, is_medical=True)

def create_maintenance(owner: str) -> Unit:
    return Unit("Maintenance", movable=False, health=80, attack=0, owner=owner, is_maintenance=True)
