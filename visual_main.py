import pygame
import sys
import math
from collections import deque

from game.game_logic import Game
from game.unit import create_soldier, create_setpoint, create_medical

# ================== 화면/상수 ==================
SCREEN_WIDTH, SCREEN_HEIGHT = 1200, 800
FPS = 60
HEX_SIZE = 28
SQRT3 = math.sqrt(3)

COLOR_BG = (35, 36, 40)
COLOR_GRID = (92, 96, 105)
COLOR_ALLY = (110, 170, 255)
COLOR_ENEMY = (255, 130, 130)
COLOR_BOUNDARY = (245, 215, 110)
COLOR_PINPOINT_ALLY = (20, 120, 255)
COLOR_PINPOINT_ENEMY = (255, 80, 80)
COLOR_GOLD = (255, 215, 0)
COLOR_TEXT = (235, 238, 242)
COLOR_PANEL = (20, 21, 24, 180)
COLOR_HL = (255, 255, 0)
COLOR_ERR = (255, 80, 80)
COLOR_OK = (140, 220, 140)
COLOR_CAPTURE = (255, 230, 120)

STEP_TIME = 0.4          # 적 진영으로 들어갈 때 한 칸 이동 시간(초)
CAPTURE_TIME = 8.0       # 적/아군 타일 점령에 필요한 시간(초)

# ================== 폰트 ==================
def load_korean_font(size=20):
    candidates = [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgunbd.ttf",
        r"C:\Windows\Fonts\NanumGothic.ttf",
        r"/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        r"/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for path in candidates:
        try:
            return pygame.font.Font(path, size)
        except Exception:
            pass
    try:
        return pygame.font.SysFont("malgungothic", size)
    except Exception:
        return pygame.font.SysFont(None, size)

# ================== 좌표/도형 ==================
def axial_to_pixel(q, r, size=HEX_SIZE, origin=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)):
    ox, oy = origin
    x = size * 1.5 * q
    y = size * (SQRT3 * (r + q/2))
    return int(ox + x), int(oy + y)

def hex_polygon(cx, cy, size=HEX_SIZE):
    pts = []
    for i in range(6):
        ang = math.radians(60 * i - 30)  # pointy-top
        pts.append((cx + size * math.cos(ang), cy + size * math.sin(ang)))
    return pts

def nearest_tile_from_pos(game, pos, origin):
    mx, my = pos
    best = None
    best_d2 = 1e18
    for (q, r), tile in game.map.tiles.items():
        cx, cy = axial_to_pixel(q, r, origin=origin)
        d2 = (mx - cx) ** 2 + (my - cy) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = tile
    return best

def hex_neighbors(game, q, r):
    return game.map.neighbors(q, r)

def hex_distance(q1, r1, q2, r2):
    dq = q1 - q2
    dr = r1 - r2
    ds = -(q1 + r1) - (-(q2 + r2))
    return max(abs(dq), abs(dr), abs(ds))

def draw_panel(surface, x, y, w, h, color_rgba):
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, color_rgba, (0, 0, w, h), border_radius=12)
    surface.blit(panel, (x, y))

# ================== BFS (좌표 튜플 기반) ==================
def bfs_path(game, start_tile, goal_tile):
    start = (start_tile.q, start_tile.r)
    goal = (goal_tile.q, goal_tile.r)
    if start == goal:
        return [start_tile]

    q = deque([start])
    prev = {start: None}
    while q:
        cq, cr = q.popleft()
        for nb in game.map.neighbors(cq, cr):
            key = (nb.q, nb.r)
            if key in prev:
                continue
            # 중간 칸은 비어 있어야 통과 (목표 칸은 key==goal일 때만 예외)
            if nb.unit is not None and key != goal:
                continue
            prev[key] = (cq, cr)
            if key == goal:
                # 경로 복원
                path_coords = []
                cur = goal
                while cur is not None:
                    path_coords.append(cur)
                    cur = prev[cur]
                path_coords.reverse()
                return [game.map.get_tile(q, r) for (q, r) in path_coords]
            q.append(key)
    return None

# ================== 규칙/도우미 ==================
def find_pinpoint_tile(game, owner='ally'):
    for t in game.map.tiles.values():
        if t.unit and t.unit.is_pinpoint and t.unit.owner == owner:
            return t
    return None

def recompute_boundaries(game):
    for tile in game.map.tiles.values():
        tile.boundary = False
    for (q, r), tile in game.map.tiles.items():
        for nb in game.map.neighbors(q, r):
            if nb.owner != tile.owner:
                tile.boundary = True
                break

def can_place_unit_on_tile(game, unit, tile):
    if tile.unit is not None:
        return False, "이미 유닛이 있습니다."
    if tile.owner != unit.owner:
        return False, "해당 진영 타일에만 설치할 수 있습니다."
    for nb in game.map.neighbors(tile.q, tile.r):
        if nb.unit and nb.unit.is_pinpoint and unit.name != "Soldier":
            return False, "핀포인트 인접 타일에는 병 유닛만 설치 가능."
    if unit.is_setpoint:
        pp = find_pinpoint_tile(game, owner=unit.owner)
        if not pp:
            return False, "핀포인트를 찾을 수 없습니다."
        if hex_distance(tile.q, tile.r, pp.q, pp.r) > 4:
            return False, "셋포인트는 핀포인트로부터 4칸 이내에만 설치 가능."
    if unit.is_medical:
        for t in game.map.tiles.values():
            if t.unit and t.unit.is_medical and t.unit.owner == unit.owner:
                return False, "보건소는 각 진영 1개만 설치 가능."
    return True, "설치 가능"

# ================== 메인 ==================
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("국가전쟁 – 유닛 구매/설치/이동/점령(양 진영 테스트)")
    clock = pygame.time.Clock()

    font = load_korean_font(22)
    font_small = load_korean_font(18)

    game = Game()
    origin = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)

    # 인벤토리: 양 진영 분리
    reserve = {
        "ally":   {"soldier": [], "setpoint": [], "medical": []},
        "enemy":  {"soldier": [], "setpoint": [], "medical": []},
    }
    selected_type = "soldier"
    control_side = "ally"     # TAB으로 ally/enemy 전환

    # 지도 위 유닛 선택/이동 (진영별)
    selected_unit_tile = None          # 현재 조종 진영의 선택된 병 유닛이 있는 타일
    active_moves = []                  # 진행 중 이동: dict(path, idx, acc, unit)
    capture_states = {}                # {(q,r): {"owner":"ally"|"enemy","remain":float,"unit_id":id(unit)}}

    # 토스트 메시지
    toasts = deque(maxlen=6)
    def toast(msg, ok=True):
        toasts.appendleft((msg, pygame.time.get_ticks(), ok))

    help_lines = [
        "조작:",
        "- TAB : 조종 진영 전환 (ALLY ↔ ENEMY)",
        "- 1/2/3 : 배치 유닛 선택 (병/셋포인트/보건소)   B: 구매(현재 진영 돈 차감)",
        "- 좌클릭: (예비→설치) / (해당 진영 병 선택 또는 목표 지정)",
        "- 우클릭: 해당 진영 유닛 회수(핀포인트 제외) / 선택 해제",
        "- G: 금광 수급(현재 진영)   SPACE: 1초 경과   T: 12초 경과   ESC: 종료",
        "- 병 이동: 아군→아군 즉시, 적 진영은 경로 따라 연속 이동",
        "- 적/아군 타일 위 병 유닛이 8초 버티면 해당 진영으로 점령",
    ]

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # ===== 입력 =====
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_TAB:
                    control_side = "enemy" if control_side == "ally" else "ally"
                    selected_unit_tile = None
                    toast(f"조종 진영: {control_side.upper()}", True)
                elif event.key == pygame.K_SPACE:
                    game.update_cooldowns()
                elif event.key == pygame.K_t:
                    for _ in range(12):
                        game.update_cooldowns()
                elif event.key == pygame.K_g:
                    game.collect_gold(control_side)
                elif event.key == pygame.K_1:
                    selected_type = "soldier"; toast("선택: 병 유닛", True)
                elif event.key == pygame.K_2:
                    selected_type = "setpoint"; toast("선택: 셋포인트", True)
                elif event.key == pygame.K_3:
                    selected_type = "medical"; toast("선택: 보건소", True)
                elif event.key == pygame.K_b:
                    try:
                        if selected_type == "soldier":
                            u = game.players[control_side].purchase_unit('soldier'); reserve[control_side]["soldier"].append(u)
                            toast(f"[{control_side}] 병 구매 완료 (-100)", True)
                        elif selected_type == "setpoint":
                            u = game.players[control_side].purchase_unit('setpoint'); reserve[control_side]["setpoint"].append(u)
                            toast(f"[{control_side}] 셋포인트 구매 완료 (-500)", True)
                        else:
                            u = game.players[control_side].purchase_unit('medical'); reserve[control_side]["medical"].append(u)
                            toast(f"[{control_side}] 보건소 구매 완료 (-1000)", True)
                    except Exception as e:
                        toast(str(e), False)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_tile = nearest_tile_from_pos(game, pygame.mouse.get_pos(), origin)
                if not mouse_tile:
                    continue

                if event.button == 3:
                    # 우클릭: 해당 진영 선택 해제/회수
                    if selected_unit_tile is not None and mouse_tile is selected_unit_tile:
                        selected_unit_tile = None
                        toast("선택 해제", True)
                    elif mouse_tile.unit and mouse_tile.unit.owner == control_side and not mouse_tile.unit.is_pinpoint:
                        u = mouse_tile.unit; mouse_tile.unit = None
                        if u.is_setpoint: reserve[control_side]["setpoint"].append(u)
                        elif u.is_medical: reserve[control_side]["medical"].append(u)
                        else: reserve[control_side]["soldier"].append(u)
                        toast(f"[{control_side}] {u.name} 회수 완료", True)
                    continue

                if event.button == 1:
                    # 1) 해당 진영 병 유닛 선택
                    if mouse_tile.unit and mouse_tile.unit.owner == control_side and mouse_tile.unit.name == "Soldier":
                        selected_unit_tile = mouse_tile
                        toast(f"[{control_side}] 병 유닛 선택", True)
                        continue

                    # 2) 선택된 병 → 목표로 이동
                    if selected_unit_tile and selected_unit_tile.unit and selected_unit_tile.unit.name == "Soldier":
                        soldier = selected_unit_tile.unit
                        if mouse_tile.unit is not None:
                            toast("목표 타일에 유닛이 있습니다.", False)
                            continue

                        # 같은 진영 내부 이동은 순간이동
                        if mouse_tile.owner == control_side and selected_unit_tile.owner == control_side:
                            mouse_tile.unit = soldier
                            selected_unit_tile.unit = None
                            selected_unit_tile = mouse_tile
                            toast("순간이동 완료", True)
                        else:
                            path = bfs_path(game, selected_unit_tile, mouse_tile)
                            if not path:
                                toast("경로가 없습니다.", False)
                            else:
                                active_moves.append({
                                    "path": path,
                                    "idx": 0,
                                    "acc": 0.0,
                                    "unit": soldier
                                })
                                selected_unit_tile.unit = None
                                selected_unit_tile = None
                                toast("이동 시작", True)
                        continue

                    # 3) 설치(예비 → 지도)
                    pool = reserve[control_side]
                    if selected_type == "soldier":
                        if not pool["soldier"]:
                            toast(f"[{control_side}] 예비 병 유닛이 없습니다. (B로 구매)", False); continue
                        candidate = pool["soldier"][0]
                    elif selected_type == "setpoint":
                        if not pool["setpoint"]:
                            toast(f"[{control_side}] 예비 셋포인트가 없습니다. (B로 구매)", False); continue
                        candidate = pool["setpoint"][0]
                    else:
                        if not pool["medical"]:
                            toast(f"[{control_side}] 예비 보건소가 없습니다. (B로 구매)", False); continue
                        candidate = pool["medical"][0]

                    candidate.owner = control_side
                    ok, reason = can_place_unit_on_tile(game, candidate, mouse_tile)
                    if not ok:
                        toast(reason, False)
                    else:
                        mouse_tile.place_unit(candidate)
                        pool[selected_type].pop(0)
                        toast(f"[{control_side}] {candidate.name} 설치 완료", True)

        # ===== 이동 업데이트 =====
        for mv in list(active_moves):
            mv["acc"] += dt
            idx = mv["idx"]
            path = mv["path"]
            if idx == 0 and path[0].unit is None:
                path[0].unit = mv["unit"]

            while mv["acc"] >= STEP_TIME:
                mv["acc"] -= STEP_TIME
                if mv["idx"] + 1 < len(path):
                    cur = path[mv["idx"]]
                    nxt = path[mv["idx"] + 1]
                    if nxt.unit is not None:
                        toast("이동이 차단되었습니다.", False)
                        active_moves.remove(mv)
                        break
                    nxt.unit = cur.unit
                    cur.unit = None
                    mv["idx"] += 1
                else:
                    active_moves.remove(mv)
                    break

        # ===== 점령 로직 (양 진영 공통) =====
        # 진행 중 상태 업데이트
        remove_keys = []
        for (q, r), state in capture_states.items():
            tile = game.map.get_tile(q, r)
            unit = tile.unit
            if not unit or unit.name != "Soldier" or unit.owner != state["owner"]:
                remove_keys.append((q, r))
                continue
            state["remain"] -= dt
            if state["remain"] <= 0:
                tile.owner = state["owner"]
                remove_keys.append((q, r))
                recompute_boundaries(game)
                toast(f"타일(q={q}, r={r}) {state['owner']} 점령 완료!", True)
        for k in remove_keys:
            capture_states.pop(k, None)

        # 새로 점령 시작/취소 판정
        for tile in game.map.tiles.values():
            if tile.unit and tile.unit.name == "Soldier" and tile.owner != tile.unit.owner:
                key = (tile.q, tile.r)
                if key not in capture_states:
                    capture_states[key] = {"owner": tile.unit.owner, "remain": CAPTURE_TIME, "unit_id": id(tile.unit)}
            else:
                capture_states.pop((tile.q, tile.r), None)

        # ===== 렌더 =====
        screen.fill(COLOR_BG)
        mouse_pos = pygame.mouse.get_pos()
        hover = nearest_tile_from_pos(game, mouse_pos, origin)

        # 타일/그리드
        for (q, r), tile in game.map.tiles.items():
            cx, cy = axial_to_pixel(q, r, origin=origin)
            poly = hex_polygon(cx, cy, HEX_SIZE - 1)
            fill = COLOR_ALLY if tile.owner == 'ally' else COLOR_ENEMY
            fill_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(fill_surface, (*fill, 42), poly)
            screen.blit(fill_surface, (0, 0))
            pygame.draw.polygon(screen, COLOR_GRID, poly, 1)

        # 경계 강조
        for tile in game.map.tiles.values():
            if tile.boundary:
                cx, cy = axial_to_pixel(tile.q, tile.r, origin=origin)
                pygame.draw.polygon(screen, COLOR_BOUNDARY, hex_polygon(cx, cy, HEX_SIZE - 1), 2)

        # 금광/유닛
        for tile in game.map.tiles.values():
            cx, cy = axial_to_pixel(tile.q, tile.r, origin=origin)
            if tile.terrain == 'gold':
                pygame.draw.circle(screen, COLOR_GOLD, (cx, cy), HEX_SIZE // 3)
                if tile.gold_cooldown > 0:
                    cd = font_small.render(f"{tile.gold_cooldown}s", True, COLOR_TEXT)
                    screen.blit(cd, (cx - cd.get_width() // 2, cy - HEX_SIZE))
            if tile.unit:
                if tile.unit.is_pinpoint:
                    col = COLOR_PINPOINT_ALLY if tile.unit.owner == 'ally' else COLOR_PINPOINT_ENEMY
                    pygame.draw.circle(screen, col, (cx, cy), HEX_SIZE // 2)
                else:
                    pygame.draw.circle(screen, COLOR_TEXT, (cx, cy), HEX_SIZE // 3, 2)

        # 점령 진행 링
        for (q, r), state in capture_states.items():
            cx, cy = axial_to_pixel(q, r, origin=origin)
            pygame.draw.circle(screen, COLOR_CAPTURE, (cx, cy), HEX_SIZE - 4, 3)
            txt = font_small.render(f"{state['remain']:.1f}s", True, COLOR_CAPTURE)
            screen.blit(txt, (cx - txt.get_width() // 2, cy - HEX_SIZE))

        # 하이라이트
        if hover:
            cx, cy = axial_to_pixel(hover.q, hover.r, origin=origin)
            pygame.draw.polygon(screen, COLOR_HL, hex_polygon(cx, cy, HEX_SIZE - 1), 2)
        if selected_unit_tile:
            cx, cy = axial_to_pixel(selected_unit_tile.q, selected_unit_tile.r, origin=origin)
            pygame.draw.polygon(screen, COLOR_OK, hex_polygon(cx, cy, HEX_SIZE - 3), 3)

        # HUD
        panel_w, panel_h = 640, 320
        draw_panel(screen, 12, 12, panel_w, panel_h, COLOR_PANEL)

        ally_money = game.players['ally'].money
        enemy_money = game.players['enemy'].money

        inv = reserve[control_side]
        inv_s = len(inv["soldier"]); inv_t = len(inv["setpoint"]); inv_m = len(inv["medical"])

        lines = [
            f"[CTRL] 조종 진영: {control_side.upper()}  |  (TAB으로 전환)",
            f"ALLY MONEY: {ally_money}   ENEMY MONEY: {enemy_money}",
            f"현재 진영 예비: 병 {inv_s} / 셋포인트 {inv_t} / 보건소 {inv_m}",
            f"선택 유형: { {'soldier':'병', 'setpoint':'셋포인트', 'medical':'보건소'}[selected_type] }",
            "",
            "단축키:",
            "TAB: 진영 전환   1/2/3: 유형 선택   B: 구매",
            "좌클릭: 설치 / (해당 진영) 병 선택·이동명령   우클릭: 회수·선택해제",
            "G: 금광 수급(현재 진영)   SPACE: 1초 경과   T: 12초 경과   ESC: 종료",
            "병 이동: 아군→아군 즉시 / 적 진영 연속 이동, 적/아군 타일 8초 점령",
        ]
        y = 24
        for ln in lines:
            screen.blit(font.render(ln, True, COLOR_TEXT), (28, y)); y += 26

        # 토스트
        base_y = panel_h + 24
        for i, (msg, ts, ok) in enumerate(toasts):
            col = COLOR_OK if ok else COLOR_ERR
            screen.blit(font_small.render(("✔ " if ok else "✖ ") + msg, True, col), (28, base_y + i * 22))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
