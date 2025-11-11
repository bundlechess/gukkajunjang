import random
from game.hex_map import HexMap
from game.player import Player

class Game:
    def __init__(self):
        self.map = HexMap(size=6)
        self.players = {'ally': Player('ally'), 'enemy': Player('enemy')}
        self.turn = 0

    def collect_gold(self, player_name):
        for tile in self.map.tiles.values():
            if tile.terrain=='gold' and tile.owner==player_name and tile.gold_cooldown<=0:
                amount = tile.gold_amount
                self.players[player_name].money += amount
                tile.gold_amount = random.randint(50,2000)
                tile.gold_cooldown = 12
                print(f"{player_name} collected {amount} gold!")

    def update_cooldowns(self):
        for tile in self.map.tiles.values():
            if tile.gold_cooldown>0:
                tile.gold_cooldown -= 1
