from typing import List
from game.unit import create_soldier, create_setpoint, create_medical

class Player:
    def __init__(self, name: str):
        self.name = name
        self.money = 5000
        self.units_inventory: List = []

    def purchase_unit(self, unit_type: str):
        if unit_type == 'soldier':
            cost = 100
            if self.money < cost:
                raise ValueError("Not enough money")
            self.money -= cost
            unit = create_soldier(self.name)
            self.units_inventory.append(unit)
            return unit

        elif unit_type == 'setpoint':
            cost = 500
            if self.money < cost:
                raise ValueError("Not enough money")
            if sum(1 for u in self.units_inventory if u.is_setpoint) >= 3:
                raise ValueError("Max 3 Setpoint units allowed")
            self.money -= cost
            unit = create_setpoint(self.name)
            self.units_inventory.append(unit)
            return unit

        elif unit_type == 'medical':
            cost = 1000
            if self.money < cost:
                raise ValueError("Not enough money")
            if any(u.is_medical for u in self.units_inventory):
                raise ValueError("Medical unit already exists")
            self.money -= cost
            unit = create_medical(self.name)
            self.units_inventory.append(unit)
            return unit

        else:
            raise ValueError("Invalid unit type")
