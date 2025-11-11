from game.game_logic import Game
import time

game = Game()
ally = game.players['ally']

print("초기 아군 돈:", ally.money)
game.collect_gold('ally')
print("금광 수급 후 돈:", ally.money)

for i in range(12):
    game.update_cooldowns()
    print(f"쿨다운 {i+1}초 경과")
    time.sleep(0.05)  # 보기용(선택)
