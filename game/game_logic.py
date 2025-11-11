import random
from game.hex_map import HexMap
from game.player import Player

class Game:
    def __init__(self):
        self.map = HexMap(size=6)
        self.players = {'ally': Player('ally'), 'enemy': Player('enemy')}
        self.heal_queue = []   # [(unit, hospital_tile, timer)]
        self.fire_timer = 0.0
        self.recent_shots = []  # [[target_tile, timer], ...]

    # =========================================================
    # 메인 업데이트: visual_main에서 매 프레임 dt로 호출
    # =========================================================
    def update_systems(self, dt=1.0):
        self._update_gold_cooldowns(dt)
        self._process_gold_mining(dt)
        self._process_setpoint_fire(dt)
        self._process_healing(dt)
        self._update_shot_effects(dt)

    # -------------------------------------------------
    # 헥스 거리 계산 (axial)
    # -------------------------------------------------
    def _hex_distance(self, q1, r1, q2, r2):
        dq = q1 - q2
        dr = r1 - r2
        ds = -(q1 + r1) - (-(q2 + r2))
        return max(abs(dq), abs(dr), abs(ds))

    # -------------------------------------------------
    # 금광 쿨다운
    # -------------------------------------------------
    def _update_gold_cooldowns(self, dt):
        for t in self.map.tiles.values():
            if t.gold_cooldown > 0:
                t.gold_cooldown -= dt
                if t.gold_cooldown < 0:
                    t.gold_cooldown = 0

    # -------------------------------------------------
    # 병 유닛이 금광에서 채굴 (시각화를 위한 t.gold_timer 유지)
    # -------------------------------------------------
    def _process_gold_mining(self, dt):
        for t in self.map.tiles.values():
            if t.terrain == 'gold' and t.unit and t.unit.name == 'Soldier':
                if t.gold_cooldown <= 0:
                    t.gold_timer = getattr(t, "gold_timer", 0.0) + dt
                    if t.gold_timer >= 5.0:
                        amount = random.randint(50, 2000)
                        owner = t.unit.owner
                        self.players[owner].money += amount
                        t.gold_cooldown = 12.0
                        t.gold_amount = amount  # 시각화용
                        t.gold_timer = 0.0
                        # print(f"[{owner}] mined {amount} gold!")
                else:
                    t.gold_timer = 0.0
            else:
                if hasattr(t, "gold_timer"):
                    if not (t.terrain == 'gold' and t.unit and t.unit.name == 'Soldier'):
                        t.gold_timer = 0.0

    # -------------------------------------------------
    # 셋포인트 포격 (가까운 병 우선 + 경계 우선, Tile set 사용하지 않도록 수정)
    # -------------------------------------------------
    def _process_setpoint_fire(self, dt):
        self.fire_timer += dt
        if self.fire_timer < 1.0:
            return
        self.fire_timer = 0.0

        for t in self.map.tiles.values():
            u = t.unit
            if not u or not u.is_setpoint:
                continue

            # 사거리 2 후보 수집 (Tile을 set에 넣지 말고 좌표 튜플로 중복 제거)
            ring1 = self.map.neighbors(t.q, t.r)  # 거리 1
            ring2_list = []
            for nb in ring1:
                ring2_list.extend(self.map.neighbors(nb.q, nb.r))  # 거리 2

            seen = set()  # {(q,r)}
            candidates = []  # (dist, -priority, tile)

            def consider_tile(tile_obj):
                key = (tile_obj.q, tile_obj.r)
                if key in seen: 
                    return
                seen.add(key)
                if tile_obj.unit and tile_obj.unit.name == "Soldier" and tile_obj.unit.owner != u.owner:
                    dist = self._hex_distance(t.q, t.r, tile_obj.q, tile_obj.r)
                    priority = 1 if getattr(tile_obj, "boundary", False) else 0  # 경계 우선
                    candidates.append((dist, -priority, tile_obj))

            for nb in ring1:
                consider_tile(nb)
            for nb2 in ring2_list:
                consider_tile(nb2)

            if not candidates:
                continue

            candidates.sort(key=lambda x: (x[0], x[1]))  # 거리 우선, 그다음 경계 우선
            target = candidates[0][2]

            # 명중 확률 40%
            if random.random() < 0.4:
                target.unit.take_damage(5)
                if target.unit.health <= 0:
                    target.unit = None
                # 폭발 시각 효과(0.5초)
                self.recent_shots.append([target, 0.5])

    # -------------------------------------------------
    # (선택) 전투 후 보건소 귀환 대기열 등록
    # -------------------------------------------------
    def send_to_hospital(self, unit):
        for t in self.map.tiles.values():
            if t.unit and t.unit.is_medical and t.unit.owner == unit.owner:
                self.heal_queue.append((unit, t, 0.0))
                break

    # -------------------------------------------------
    # 보건소 회복: 3초당 HP +1 (최대 20)
    # -------------------------------------------------
    def _process_healing(self, dt):
        done = []
        for i, (u, hosp, timer) in enumerate(self.heal_queue):
            if not hosp.unit or not hosp.unit.is_medical:
                done.append(i)
                continue
            timer += dt
            if timer >= 3.0:
                u.health = min(20, u.health + 1)
                timer = 0.0
            if u.health >= 20:
                done.append(i)
            self.heal_queue[i] = (u, hosp, timer)
        for i in reversed(done):
            self.heal_queue.pop(i)

    # -------------------------------------------------
    # 폭발 링 시각 효과 타이머 관리
    # -------------------------------------------------
    def _update_shot_effects(self, dt):
        for shot in list(self.recent_shots):
            shot[1] -= dt
            if shot[1] <= 0:
                self.recent_shots.remove(shot)
