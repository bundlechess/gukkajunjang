# client.py

import pygame
import socket
import threading
import time
import sys
import pickle

# --------------------------------------------------------------------
# ⚠️ visual_main.py의 모든 내용 (상수, 폰트, 그리기 함수, 헬퍼 함수 등)을 
#    이곳에 그대로 복사/붙여넣기 해야 합니다.
# --------------------------------------------------------------------
import pygame
import sys
import math
import random
import os
from collections import deque

from game.game_logic import Game
from game.unit import create_soldier, create_setpoint, create_medical, create_wall

# ================== 화면/상수 ==================
LOGICAL_W, LOGICAL_H = 1280, 720   # 고정 논리 해상도
FPS = 45
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
COLOR_PANEL = (20, 21, 24, 140)
COLOR_BUTTON = (32, 34, 38, 200)
COLOR_BUTTON_HL = (60, 64, 72, 220)
COLOR_HL = (255, 255, 0)
COLOR_ERR = (255, 80, 80)
COLOR_OK = (140, 220, 140)
COLOR_CAPTURE = (255, 230, 120)
COLOR_BAR_BG = (60, 60, 70)
COLOR_BAR_FG = (255, 220, 120)

# 체력바 색상 (아군: 초록/회색, 적군: 빨강/회색)
COLOR_HP_ALLY  = (80, 220, 100)
COLOR_HP_ENEMY = (220, 80, 80)
COLOR_HP_BG    = (90, 90, 90)

# 💥 데미지 팝업 색상 (가해자 기준)
COLOR_DMG_ALLY  = (110, 170, 255)
COLOR_DMG_ENEMY = (255, 110, 110)

# 벽 부수기 표시용 색
COLOR_WALL_BREAK = (140, 200, 255)

STEP_TIME = 0.4
CAPTURE_TIME = 8.0
COMBAT_TICK = 2.0     # 전투는 2초마다 1번 계산
COMBAT_SPEED = 0.6    # 전체 전투 속도 배율
DEBUG_OVERLAY = False  # F9로 HP/ATK 표시 토글

# ================== 폰트/텍스트 캐시 ==================
_font_cache, _text_cache = {}, {}
def load_korean_font(size=20):
    key = ("font", size)
    if key in _font_cache:
        return _font_cache[key]
    candidates = [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgunbd.ttf",
        r"C:\Windows\Fonts\NanumGothic.ttf",
        r"/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        r"/System/Library/Fonts\AppleSDGothicNeo.ttc",
    ]
    for path in candidates:
        try:
            f = pygame.font.Font(path, size)
            _font_cache[key] = f
            return f
        except Exception:
            pass
    try:
        f = pygame.font.SysFont("malgungothic", size)
    except Exception:
        f = pygame.font.SysFont(None, size)
    _font_cache[key] = f
    return f

def render_text_cached(font, text, color):
    key = (id(font), text, color)
    surf = _text_cache.get(key)
    if surf is None:
        surf = font.render(text, True, color)
        _text_cache[key] = surf
    return surf

# ================== 이미지 로더 ==================
IMAGE_CACHE = {}

def load_unit_image(name, owner):
    """
    name: 'Soldier', 'Wall', 'Setpoint', 'Medical', 'Pinpoint'
    owner: 'ally' / 'enemy'
    파일명: assets/{name_lower}_{owner}.png
    """
    key = (name, owner)
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]

    fname = f"{name.lower()}_{owner}.png"
    path = os.path.join("assets", fname)

    if not os.path.exists(path):
        # print 경고만, 나머지는 fallback 그리기
        print(f"[WARN] 이미지 파일 없음: {path}")
        IMAGE_CACHE[key] = None
        return None

    try:
        img = pygame.image.load(path).convert_alpha()
    except Exception as e:
        print(f"[ERROR] 이미지 로드 실패: {path} — {e}")
        IMAGE_CACHE[key] = None
        return None

    IMAGE_CACHE[key] = img
    return img

def scale_unit_image(img):
    if img is None:
        return None
    target = int(HEX_SIZE * 1.2)   # 유닛 이미지 크기 (조정 가능)
    return pygame.transform.smoothscale(img, (target, target))

# ================== 좌표/도형 ==================
ORIGIN = (LOGICAL_W // 2, LOGICAL_H // 2 + 20)

def axial_to_pixel(q, r, size=HEX_SIZE, origin=ORIGIN):
    ox, oy = origin
    x = size * 1.5 * q
    y = size * (SQRT3 * (r + q/2))
    return int(ox + x), int(oy + y)

def hex_polygon(cx, cy, size=HEX_SIZE):
    pts = []
    for i in range(6):
        ang = math.radians(60 * i - 30)
        pts.append((cx + size * math.cos(ang), cy + size * math.sin(ang)))
    return pts

def nearest_tile_from_pos(game, pos, origin=ORIGIN):
    mx, my = pos
    best, best_d2 = None, 1e18
    for (q, r), tile in game.map.tiles.items():
        cx, cy = axial_to_pixel(q, r, origin=origin)
        d2 = (mx - cx) ** 2 + (my - cy) ** 2
        if d2 < best_d2:
            best_d2, best = d2, tile
    return best

def hex_distance(q1, r1, q2, r2):
    dq = q1 - q2
    dr = r1 - r2
    ds = -(q1 + r1) - (-(q2 + r2))
    return max(abs(dq), abs(dr), abs(ds))

def draw_panel(surface, x, y, w, h, color_rgba):
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, color_rgba, (0, 0, w, h), border_radius=12)
    surface.blit(panel, (x, y))

def draw_button(surface, rect, label, font, hovered=False):
    x, y, w, h = rect
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, COLOR_BUTTON_HL if hovered else COLOR_BUTTON,
                     (0, 0, w, h), border_radius=10)
    surface.blit(panel, (x, y))
    txt = render_text_cached(font, label, COLOR_TEXT)
    surface.blit(txt, (x + (w - txt.get_width())//2, y + (h - txt.get_height())//2))

# ================== BFS (좌표 튜플 기반) ==================
from collections import deque as _deque
def bfs_path(game, start_tile, goal_tile):
    """
    - 일반 유닛(unit) 기준 이동 경로 탐색
    - 벽(wall)은:
        * 같은 진영의 벽: 통과/도착 가능
        * 적 진영 벽  : 통과 불가, 단 '목표 타일(goal)'이면 도착까지는 허용
          (목표 타일 도착 시, 실제 이동 처리에서 '벽 부수기 타이머' 시작)
    """
    start = (start_tile.q, start_tile.r)
    goal = (goal_tile.q, goal_tile.r)
    if start == goal:
        return [start_tile]

    mover_owner = None
    if start_tile.unit:
        mover_owner = start_tile.unit.owner

    q = _deque([start])
    prev = {start: None}

    while q:
        cq, cr = q.popleft()
        for nb in game.map.neighbors(cq, cr):
            key = (nb.q, nb.r)
            if key in prev:
                continue

            # 다른 일반 유닛이 있으면 통과 불가 (단 goal은 예외 -> 전투/벽 파괴용)
            if nb.unit is not None and key != goal:
                continue

            # 벽 처리: 적의 벽이면 통과 불가 (goal은 예외)
            wall = getattr(nb, "wall", None)
            if wall is not None and mover_owner is not None:
                if wall.owner != mover_owner and key != goal:
                    continue

            prev[key] = (cq, cr)
            if key == goal:
                path_coords, cur = [], goal
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
    """
    설치 규칙:
    - 모든 유닛: 자기 진영(owner) 타일에만 설치 가능
    - 병: 일반 유닛(unit)이 없으면 설치 가능, 벽(wall)은 있어도 OK (아군 벽 위 설치 허용)
    - 벽: 해당 타일에 다른 일반 유닛이 없어야 하고, 기존 벽이 없어야 함
    - 셋포인트/보건소: 일반 유닛이 없어야 함, 핀포인트 인접 제한 적용
    """
    # 소유권 체크
    if tile.owner != unit.owner:
        return False, "해당 진영 타일에만 설치할 수 있습니다."

    # 병 유닛: 벽과 겹치기 허용, 일반 유닛만 막음
    if unit.name == "Soldier":
        if tile.unit is not None:
            return False, "이미 유닛이 있습니다."

    # 벽 유닛
    elif getattr(unit, "is_wall", False):
        if getattr(tile, "wall", None) is not None:
            return False, "이미 벽 유닛이 있습니다."
        if tile.unit is not None:
            return False, "해당 칸에 다른 유닛이 있어 벽을 설치할 수 없습니다."

    # 그 외(셋포인트, 보건소 등): 일반 유닛이 없어야 함
    else:
        if tile.unit is not None:
            return False, "이미 유닛이 있습니다."

    # 핀포인트 인접 제한:
    #  - 병/벽은 예외 (둘 다 허용)
    for nb in game.map.neighbors(tile.q, tile.r):
        if nb.unit and nb.unit.is_pinpoint and unit.name not in ("Soldier", "Wall"):
            return False, "핀포인트 인접 타일에는 병/벽 유닛만 설치 가능."

    # 셋포인트 거리 제한
    if unit.is_setpoint:
        pp = find_pinpoint_tile(game, owner=unit.owner)
        if not pp:
            return False, "핀포인트를 찾을 수 없습니다."
        if hex_distance(tile.q, tile.r, pp.q, pp.r) > 4:
            return False, "셋포인트는 핀포인트로부터 4칸 이내만 설치 가능."

    # 보건소는 Player에서 1개 제한 이미 걸려 있음
    return True, "설치 가능"

# --- 전투 중복 등록 방지용 헬퍼 ---
def add_battle_once(battles, tile, attacker, defender):
    for b in battles:
        if b["tile"] is tile:
            return False
    battles.append({"tile": tile, "att": attacker, "def": defender})
    return True

# ================== 텍스트 유틸(외곽선) ==================
def blit_text_outline(surface, text, font, x, y,
                      inner_color, outline_color=(0, 0, 0),
                      outline_w=2, alpha=255):
    base = font.render(text, True, inner_color)
    if alpha < 255:
        base.set_alpha(alpha)
    oxys, w = [], outline_w
    for dx in range(-w, w+1):
        for dy in range(-w, w+1):
            if dx*dx + dy*dy <= w*w and not (dx == 0 and dy == 0):
                oxys.append((dx, dy))
    out = font.render(text, True, outline_color)
    if alpha < 255:
        out.set_alpha(alpha)
    for dx, dy in oxys:
        surface.blit(out, (x + dx, y + dy))
    surface.blit(base, (x, y))

# ================== HP 바 유틸 ==================
def draw_hp_bar(screen, cx, cy, hp, max_hp, owner, dy=0):
    """
    병 유닛용 HP 바.
    owner: 'ally' 또는 'enemy'
    dy: 기준 위치에서의 세로 오프셋 (전투 중 위/아래 분리용)
    """
    max_hp = float(max_hp)
    hp = max(0.0, min(float(hp), max_hp))
    ratio = hp / max_hp if max_hp > 0 else 0.0

    bar_w = HEX_SIZE * 1.4
    bar_h = 5
    bx = cx - bar_w / 2
    by = cy + HEX_SIZE * 0.55 + dy

    # 회색 배경
    pygame.draw.rect(screen, COLOR_HP_BG, (bx, by, bar_w, bar_h), border_radius=3)

    # 아군/적군에 따라 체력 색상
    if owner == "ally":
        fg = COLOR_HP_ALLY
    else:
        fg = COLOR_HP_ENEMY

    # 남은 체력 부분
    pygame.draw.rect(screen, fg, (bx, by, bar_w * ratio, bar_h), border_radius=3)

    # 테두리
    pygame.draw.rect(screen, (20, 20, 20), (bx, by, bar_w, bar_h), 1, border_radius=3)

# ================== 메인 ==================
def main():
    pygame.init()
    pygame.display.set_caption("국가전쟁 – SCALED 전체화면(좌표 고정)")
    screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.SCALED)
    clock = pygame.time.Clock()

    toggle_cooldown = 0.0
    combat_accum = 0.0           # 전투 누적 타이머
    combat_speed = 0.6           # 전투 전체 배율(기본 60%)

    font = load_korean_font(22)
    font_small = load_korean_font(18)
    popup_font = load_korean_font(28)

    game = Game()

    reserve = {
        "ally":   {"soldier": [], "setpoint": [], "medical": [], "wall": []},
        "enemy":  {"soldier": [], "setpoint": [], "medical": [], "wall": []},
    }
    selected_type = "soldier"
    control_side = "ally"

    selected_unit_tile = None
    active_moves = []
    capture_states = {}
    wall_break_states = {}   # {(q,r): {"owner": 'ally'/'enemy', "remain": 10.0}}
    battles = []

    toasts = deque(maxlen=7)
    def toast(msg, ok=True):
        toasts.appendleft((msg, pygame.time.get_ticks(), ok))

    damage_popups = []
    def add_damage_popup(x, y, text, color=(255, 90, 90), life=1.2, vy=-16):
        if len(damage_popups) >= 16:
            del damage_popups[0: len(damage_popups)-15]
        damage_popups.append([x, y, text, color, life, vy, life])

    prev_gold_cd = {}

    # ===== HUD/전체화면 상태 =====
    hud_visible = True
    is_fullscreen = False

    def apply_display_mode():
        flags = pygame.SCALED
        if is_fullscreen:
            flags |= pygame.FULLSCREEN
        pygame.display.set_mode((LOGICAL_W, LOGICAL_H), flags)
        pygame.event.clear(pygame.VIDEORESIZE)

    def get_button_rects():
        hud_rect = (12, 12, 90, 36)
        fs_rect  = (LOGICAL_W - 12 - 120, 12, 120, 36)
        return hud_rect, fs_rect

    # ===== 맵 캐시 =====
    map_surface = None
    border_surface = None
    map_dirty = True

    def rebuild_map_cache():
        nonlocal map_surface, border_surface, map_dirty
        map_surface = pygame.Surface((LOGICAL_W, LOGICAL_H))
        map_surface.fill((0, 0, 0))
        for (q, r), tile in game.map.tiles.items():
            cx, cy = axial_to_pixel(q, r, origin=ORIGIN)
            poly = hex_polygon(cx, cy, HEX_SIZE - 1)
            fill = COLOR_ALLY if tile.owner == 'ally' else COLOR_ENEMY
            pygame.draw.polygon(map_surface, fill, poly)
            pygame.draw.polygon(map_surface, COLOR_GRID, poly, 1)
        border_surface = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        for tile in game.map.tiles.values():
            if tile.boundary:
                cx, cy = axial_to_pixel(tile.q, tile.r, origin=ORIGIN)
                pygame.draw.polygon(border_surface, COLOR_BOUNDARY,
                                    hex_polygon(cx, cy, HEX_SIZE - 1), 2)
        map_dirty = False

    # ===== HUD 캐시 =====
    hud_surface = None
    hud_dirty = True
    last_hud_snapshot = None

    def build_hud_surface():
        nonlocal hud_surface, hud_dirty, last_hud_snapshot
        panel_w, panel_h = 700, 356
        hud_surface = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        draw_panel(hud_surface, 0, 0, panel_w, panel_h, COLOR_PANEL)
        ally_money = game.players['ally'].money
        enemy_money = game.players['enemy'].money
        inv = reserve[control_side]
        inv_s = len(inv["soldier"])
        inv_t = len(inv["setpoint"])
        inv_m = len(inv["medical"])
        inv_w = len(inv["wall"])
        type_name_map = {
            "soldier": "병",
            "setpoint": "셋포인트",
            "medical": "보건소",
            "wall": "벽",
        }
        lines = [
            f"[CTRL] 조종 진영: {control_side.upper()}  |  TAB 전환  |  F11: 전체화면",
            f"ALLY MONEY: {ally_money}   ENEMY MONEY: {enemy_money}",
            f"현재 진영 예비: 병 {inv_s} / 셋포인트 {inv_t} / 보건소 {inv_m} / 벽 {inv_w}",
            f"선택 유형: {type_name_map.get(selected_type, selected_type)}",
            f"전투 속도: {combat_speed:.1f}x   (F5 느림/0.5 · F6 보통/0.8 · F7 빠름/1.0)",
            "",
            "단축키:",
            "TAB: 진영 전환   1/2/3/4: 유형 선택   B: 구매",
            "좌클릭: 설치 / (해당 진영) 병 선택·이동명령   우클릭: 회수·선택해제",
            "SPACE: 1초 경과   T: 12초 경과   ESC: 종료",
            "전투: 타일 소유=유닛 소유 시 ×1.5, 다르면 ×0.5",
            "채굴: 금광에서 병 5초 유지 → 획득, 이후 12초 쿨다운",
        ]
        y = 12
        for ln in lines:
            hud_surface.blit(render_text_cached(font, ln, COLOR_TEXT), (16, y))
            y += 26
        y = panel_h - 12 - 22 * min(len(toasts), 7)
        for i, (msg, ts, ok) in enumerate(toasts):
            col = COLOR_OK if ok else COLOR_ERR
            hud_surface.blit(
                render_text_cached(font_small, ("✔ " if ok else "✖ ") + msg, col),
                (16, y + i * 22),
            )
        last_hud_snapshot = (
            control_side, selected_type, ally_money, enemy_money,
            inv_s, inv_t, inv_m, inv_w,
            tuple(toasts), round(combat_speed, 2),
        )
        hud_dirty = False

    def check_hud_dirty():
        nonlocal hud_dirty
        ally_money = game.players['ally'].money
        enemy_money = game.players['enemy'].money
        inv = reserve[control_side]
        snap = (
            control_side, selected_type, ally_money, enemy_money,
            len(inv["soldier"]), len(inv["setpoint"]),
            len(inv["medical"]), len(inv["wall"]),
            tuple(toasts), round(combat_speed, 2),
        )
        if last_hud_snapshot != snap:
            hud_dirty = True

    # ================== 루프 ==================
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        toggle_cooldown = max(0.0, toggle_cooldown - dt)
        mouse_pos = pygame.mouse.get_pos()
        hud_btn_rect, fs_btn_rect = get_button_rects()

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
                    hud_dirty = True
                elif event.key == pygame.K_SPACE:
                    game.update_systems(1.0)
                elif event.key == pygame.K_t:
                    for _ in range(12):
                        game.update_systems(1.0)
                elif event.key == pygame.K_g:
                    toast("금광은 병 유닛이 5초 채굴로 획득합니다.", True)
                elif event.key == pygame.K_1:
                    selected_type = "soldier"
                    toast("선택: 병 유닛", True)
                    hud_dirty = True
                elif event.key == pygame.K_2:
                    selected_type = "setpoint"
                    toast("선택: 셋포인트", True)
                    hud_dirty = True
                elif event.key == pygame.K_3:
                    selected_type = "medical"
                    toast("선택: 보건소", True)
                    hud_dirty = True
                elif event.key == pygame.K_4:
                    selected_type = "wall"
                    toast("선택: 벽 유닛", True)
                    hud_dirty = True
                elif event.key == pygame.K_b:
                    try:
                        if selected_type == "soldier":
                            u = game.players[control_side].purchase_unit('soldier')
                            reserve[control_side]["soldier"].append(u)
                        elif selected_type == "setpoint":
                            u = game.players[control_side].purchase_unit('setpoint')
                            reserve[control_side]["setpoint"].append(u)
                        elif selected_type == "medical":
                            u = game.players[control_side].purchase_unit('medical')
                            reserve[control_side]["medical"].append(u)
                        elif selected_type == "wall":
                            u = game.players[control_side].purchase_unit('wall')
                            reserve[control_side]["wall"].append(u)
                        else:
                            raise ValueError("알 수 없는 유닛 타입입니다.")
                        toast(f"[{control_side}] {u.name} 구매 완료", True)
                        hud_dirty = True
                    except Exception as e:
                        toast(str(e), False)
                        hud_dirty = True
                elif event.key == pygame.K_F11:
                    if toggle_cooldown <= 0:
                        is_fullscreen = not is_fullscreen
                        apply_display_mode()
                        toggle_cooldown = 0.25
                elif event.key == pygame.K_F5:
                    combat_speed = 0.5
                    toast("전투 속도 0.5x (느림)", True)
                    hud_dirty = True
                elif event.key == pygame.K_F6:
                    combat_speed = 0.8
                    toast("전투 속도 0.8x (보통)", True)
                    hud_dirty = True
                elif event.key == pygame.K_F7:
                    combat_speed = 1.0
                    toast("전투 속도 1.0x (빠름)", True)
                    hud_dirty = True
                elif event.key == pygame.K_F9:
                    global DEBUG_OVERLAY
                    DEBUG_OVERLAY = not DEBUG_OVERLAY
                    toast("디버그 오버레이 " + ("ON" if DEBUG_OVERLAY else "OFF"), True)
                    hud_dirty = True

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # 버튼 우선
                    if pygame.Rect(hud_btn_rect).collidepoint(mouse_pos):
                        hud_visible = not hud_visible
                        toast("HUD 숨김" if not hud_visible else "HUD 표시", True)
                        continue
                    if pygame.Rect(fs_btn_rect).collidepoint(mouse_pos):
                        if toggle_cooldown <= 0:
                            is_fullscreen = not is_fullscreen
                            apply_display_mode()
                            toggle_cooldown = 0.25
                        continue

                mouse_tile = nearest_tile_from_pos(game, mouse_pos, origin=ORIGIN)
                if not mouse_tile:
                    continue

                # 우클릭: 선택 해제/유닛 회수 (벽 회수는 일단 제외)
                if event.button == 3:
                    if selected_unit_tile is not None and mouse_tile is selected_unit_tile:
                        selected_unit_tile = None; toast("선택 해제", True)
                    elif mouse_tile.unit and mouse_tile.unit.owner == control_side and not mouse_tile.unit.is_pinpoint:
                        u = mouse_tile.unit
                        # 전투를 한 번이라도 수행한 병 유닛은 회수 불가
                        if u.name == "Soldier" and getattr(u, "has_fought", False):
                            toast("전투를 경험한 병 유닛은 회수할 수 없습니다.", False)
                        else:
                            mouse_tile.unit = None
                            pool = reserve[control_side]
                            if u.is_setpoint: pool["setpoint"].append(u)
                            elif u.is_medical: pool["medical"].append(u)
                            else: pool["soldier"].append(u)
                            toast(f"[{control_side}] {u.name} 회수 완료", True); hud_dirty = True
                    continue

                # 좌클릭: 선택/이동/설치
                if event.button == 1:
                    # (해당 진영) 병 선택
                    if mouse_tile.unit and mouse_tile.unit.owner == control_side and mouse_tile.unit.name == "Soldier":
                        selected_unit_tile = mouse_tile
                        toast(f"[{control_side}] 병 유닛 선택", True)
                        continue

                    # 병 이동 명령
                    if selected_unit_tile and selected_unit_tile.unit and selected_unit_tile.unit.name == "Soldier":
                        soldier = selected_unit_tile.unit

                        # 같은 진영 영역 내부에서 순간이동/전투 처리
                        if mouse_tile.owner == control_side and selected_unit_tile.owner == control_side:
                            if mouse_tile.unit and mouse_tile.unit.name == "Soldier" and mouse_tile.unit.owner != control_side:
                                if add_battle_once(battles, mouse_tile, soldier, mouse_tile.unit):
                                    selected_unit_tile.unit = None
                                    selected_unit_tile = None
                                    toast("전투 시작!", True)
                            else:
                                if mouse_tile.unit is None:
                                    mouse_tile.unit = soldier
                                    selected_unit_tile.unit = None
                                    selected_unit_tile = mouse_tile
                                    toast("순간이동 완료", True)
                                else:
                                    toast("목표 타일에 유닛이 있습니다.", False)
                            continue

                        # 그 외: BFS로 경로 찾기
                        path = bfs_path(game, selected_unit_tile, mouse_tile)
                        if not path:
                            toast("경로가 없습니다.", False)
                        else:
                            active_moves.append({
                                "path": path,
                                "idx": 0,
                                "acc": 0.0,
                                "unit": soldier,
                            })
                            selected_unit_tile.unit = None
                            selected_unit_tile = None
                            toast("이동 시작", True)
                        continue

                    # 설치
                    pool = reserve[control_side]
                    if selected_type == "soldier":
                        if not pool["soldier"]:
                            toast(f"[{control_side}] 예비 병 유닛이 없습니다. (B로 구매)", False)
                            continue
                        candidate = pool["soldier"][0]
                    elif selected_type == "setpoint":
                        if not pool["setpoint"]:
                            toast(f"[{control_side}] 예비 셋포인트가 없습니다. (B로 구매)", False)
                            continue
                        candidate = pool["setpoint"][0]
                    elif selected_type == "medical":
                        if not pool["medical"]:
                            toast(f"[{control_side}] 예비 보건소가 없습니다. (B로 구매)", False)
                            continue
                        candidate = pool["medical"][0]
                    elif selected_type == "wall":
                        if not pool["wall"]:
                            toast(f"[{control_side}] 예비 벽 유닛이 없습니다. (B로 구매)", False)
                            continue
                        candidate = pool["wall"][0]
                    else:
                        toast("알 수 없는 유닛 타입입니다.", False)
                        continue

                    candidate.owner = control_side
                    ok, reason = can_place_unit_on_tile(game, candidate, mouse_tile)
                    if not ok:
                        toast(reason, False)
                    else:
                        mouse_tile.place_unit(candidate)
                        pool[selected_type].pop(0)
                        toast(f"[{control_side}] {candidate.name} 설치 완료", True)
                        hud_dirty = True

        # ===== 시스템 업데이트 =====
        game.update_systems(dt)

        # ===== 이동 업데이트 =====
        for mv in list(active_moves):
            mv["acc"] += dt
            idx = mv["idx"]
            path = mv["path"]
            unit = mv["unit"]
            if idx == 0 and path[0].unit is None:
                path[0].unit = unit
            while mv["acc"] >= STEP_TIME:
                mv["acc"] -= STEP_TIME
                if mv["idx"] + 1 < len(path):
                    cur = path[mv["idx"]]
                    nxt = path[mv["idx"] + 1]
                    is_last_step = (mv["idx"] + 1 == len(path) - 1)

                    # 마지막 칸이 적 벽이고, 그 칸에 적 병이 없을 때: 벽 파괴 시작
                    if is_last_step and getattr(nxt, "wall", None) is not None \
                       and nxt.wall.owner != unit.owner \
                       and (nxt.unit is None or nxt.unit.owner == unit.owner):
                        nxt.unit = unit
                        cur.unit = None
                        wall_break_states[(nxt.q, nxt.r)] = {
                            "owner": unit.owner,
                            "remain": 10.0,
                        }
                        active_moves.remove(mv)
                        toast("벽 파괴 시작!", True)
                        break

                    # 마지막 칸이 적 병이면 전투
                    if is_last_step and nxt.unit and nxt.unit.name == "Soldier" and nxt.unit.owner != unit.owner:
                        if add_battle_once(battles, nxt, unit, nxt.unit):
                            cur.unit = None
                            active_moves.remove(mv)
                            toast("전투 시작!", True)
                        break

                    # 그 외: 일반 유닛이 있으면 차단
                    if nxt.unit is not None:
                        toast("이동이 차단되었습니다.", False)
                        active_moves.remove(mv)
                        break

                    # 정상 이동
                    nxt.unit = cur.unit
                    cur.unit = None
                    mv["idx"] += 1
                else:
                    active_moves.remove(mv)
                    break

        # ===== 전투 처리 (고정 틱 기반) =====
        combat_accum += dt
        if battles:
            if combat_accum >= COMBAT_TICK:
                tick = COMBAT_TICK
                finished_battles = []

                for i, b in enumerate(battles):
                    tile = b["tile"]
                    att = b["att"]
                    deff = b["def"]

                    if att is None or deff is None:
                        finished_battles.append(i)
                        continue

                    # 기본 DPS (영향 전: 순수 공격력 × 전투 속도)
                    base_att = att.attack * COMBAT_SPEED
                    base_def = deff.attack * COMBAT_SPEED

                    # 전투에 참여한 병 유닛은 '전투 경험 있음' 표시
                    att.has_fought = True
                    deff.has_fought = True

                    # 평소 배율 (버프/디버프)
                    att_mul_normal = 1.5 if tile.owner == att.owner else 0.5
                    def_mul_normal = 1.5 if tile.owner == deff.owner else 0.5

                    # 🔹 치명타 판정 (병 유닛만 20%)
                    crit_att = False
                    crit_def = False
                    if getattr(att, "name", "") == "Soldier" and random.random() < 0.2:
                        crit_att = True
                    if getattr(deff, "name", "") == "Soldier" and random.random() < 0.2:
                        crit_def = True

                    # 🔹 치명타 시: 디버프(적 영역 0.5배)만 무시
                    #  - 자기 영역(버프 1.5배)은 그대로
                    if crit_att and tile.owner != att.owner:
                        att_mul = 1.0     # 디버프 제거
                    else:
                        att_mul = att_mul_normal

                    if crit_def and tile.owner != deff.owner:
                        def_mul = 1.0     # 디버프 제거
                    else:
                        def_mul = def_mul_normal

                    # 최종 데미지 계산
                    dmg_to_def = base_att * att_mul * tick
                    dmg_to_att = base_def * def_mul * tick

                    # 치명타 배율 (최종 피해 × 2배)
                    if crit_att:
                        dmg_to_def *= 2.0
                    if crit_def:
                        dmg_to_att *= 2.0

                    deff.take_damage(dmg_to_def)
                    att.take_damage(dmg_to_att)

                    shown_def = max(1, int(round(dmg_to_def))) if dmg_to_def > 0 else 0
                    shown_att = max(1, int(round(dmg_to_att))) if dmg_to_att > 0 else 0

                    cx, cy = axial_to_pixel(tile.q, tile.r)
                    col_from_att = COLOR_DMG_ALLY if att.owner == 'ally' else COLOR_DMG_ENEMY
                    col_from_def = COLOR_DMG_ALLY if deff.owner == 'ally' else COLOR_DMG_ENEMY

                    if shown_def > 0:
                        text_def = f"-{shown_def}" + ("!" if crit_att else "")
                        add_damage_popup(
                            cx + 18,
                            cy - HEX_SIZE * 0.4,
                            text_def,
                            col_from_att,
                            life=1.2,
                            vy=-12,
                        )
                    if shown_att > 0:
                        text_att = f"-{shown_att}" + ("!" if crit_def else "")
                        add_damage_popup(
                            cx - 18,
                            cy - HEX_SIZE * 0.15,
                            text_att,
                            col_from_def,
                            life=1.2,
                            vy=-12,
                        )

                    # 일반 유닛 vs 유닛 전투 처리
                    if not att.is_alive() and not deff.is_alive():
                        tile.unit = None
                        finished_battles.append(i)
                    elif not deff.is_alive():
                        tile.unit = att
                        finished_battles.append(i)
                    elif not att.is_alive():
                        tile.unit = deff
                        finished_battles.append(i)

                for i in reversed(finished_battles):
                    battles.pop(i)

                combat_accum -= COMBAT_TICK
        else:
            # 전투가 없을 땐 누적 타이머 초기화
            combat_accum = 0.0

        # ===== 벽 파괴 로직 =====
        remove_wall_keys = []
        for (q, r), state in list(wall_break_states.items()):
            tile = game.map.get_tile(q, r)
            if not tile:
                remove_wall_keys.append((q, r))
                continue

            wall = getattr(tile, "wall", None)

            # 아직도 '적 벽'이 있어야 함
            if wall is None or wall.owner == state["owner"]:
                remove_wall_keys.append((q, r))
                continue

            # 같은 진영 병 유닛이 그 칸에 서 있어야 함
            u = tile.unit
            if not u or u.name != "Soldier" or u.owner != state["owner"]:
                remove_wall_keys.append((q, r))
                continue

            state["remain"] -= dt
            if state["remain"] <= 0:
                tile.wall = None
                remove_wall_keys.append((q, r))
                toast(f"벽(q={q}, r={r}) 파괴 완료!", True)

        for k in remove_wall_keys:
            wall_break_states.pop(k, None)

        # ===== 점령 로직 =====
        remove_keys, owner_changed = [], False
        for (q, r), state in list(capture_states.items()):
            tile = game.map.get_tile(q, r)
            unit = tile.unit if tile else None

            # 병이 계속 서 있고, 벽이 없어야 점령 진행
            if (not tile or
                not unit or
                unit.name != "Soldier" or
                unit.owner != state["owner"] or
                getattr(tile, "wall", None) is not None):
                remove_keys.append((q, r))
                continue

            # 🔹 이 타일에서 전투가 진행 중이면 점령 타이머를 멈춘다
            in_battle = any(b["tile"] is tile for b in battles)
            if in_battle:
                # 전투가 끝날 때까지 시간 감소 없음
                continue

            state["remain"] -= dt
            if state["remain"] <= 0:
                if tile.owner != state["owner"]:
                    tile.owner = state["owner"]
                    owner_changed = True
                remove_keys.append((q, r))
                recompute_boundaries(game)
                toast(f"타일(q={q}, r={r}) {state['owner']} 점령 완료!", True)

        for k in remove_keys:
            capture_states.pop(k, None)

        # 점령 시작 조건: 적 타일 + 병 + 벽이 없어야 함
        for tile in game.map.tiles.values():
            if (tile.unit and tile.unit.name == "Soldier"
                and tile.owner != tile.unit.owner
                and getattr(tile, "wall", None) is None):
                key = (tile.q, tile.r)
                if key not in capture_states:
                    capture_states[key] = {"owner": tile.unit.owner,
                                           "remain": CAPTURE_TIME}
            else:
                capture_states.pop((tile.q, tile.r), None)
        if owner_changed:
            map_dirty = True

        # ===== 팝업 업데이트 =====
        for dp in list(damage_popups):
            dp[4] -= dt
            dp[1] += dp[5] * dt
            dp[5] *= 0.96
            if dp[4] <= 0:
                damage_popups.remove(dp)

        # ===== 맵 캐시 재빌드 =====
        if map_dirty or map_surface is None or border_surface is None:
            rebuild_map_cache()

        # ===== 렌더 =====
        screen.fill(COLOR_BG)
        screen.blit(map_surface, (0, 0))
        screen.blit(border_surface, (0, 0))

        hover = nearest_tile_from_pos(game, mouse_pos, origin=ORIGIN)

        # 전투 중인 타일 좌표들 (이미지/HP 바 겹침 처리용)
        battle_tiles = {(b["tile"].q, b["tile"].r) for b in battles if b["tile"] is not None}

        # 금광/유닛/벽 렌더
        for (q, r), tile in game.map.tiles.items():
            cx, cy = axial_to_pixel(q, r, origin=ORIGIN)

            # 금광
            if tile.terrain == 'gold':
                pygame.draw.circle(screen, COLOR_GOLD, (cx, cy), HEX_SIZE // 3)
                timer = getattr(tile, "gold_timer", 0.0)
                if tile.unit and tile.unit.name == "Soldier" and tile.gold_cooldown <= 0:
                    w = HEX_SIZE * 1.4
                    h = 6
                    x = cx - w/2
                    y = cy + HEX_SIZE * 0.6
                    pygame.draw.rect(screen, COLOR_BAR_BG, (x, y, w, h), border_radius=3)
                    ratio = max(0.0, min(1.0, timer / 5.0))
                    pygame.draw.rect(screen, COLOR_BAR_FG, (x, y, w * ratio, h),
                                     border_radius=3)
                if tile.gold_cooldown > 0:
                    cd = render_text_cached(font_small,
                                            f"{int(tile.gold_cooldown)}s",
                                            COLOR_TEXT)
                    screen.blit(cd, (cx - cd.get_width() // 2, cy - HEX_SIZE))

            # 벽 (배경 레이어)
            wall = getattr(tile, "wall", None)
            if wall is not None:
                wall_img = load_unit_image("Wall", wall.owner)
                if wall_img:
                    wimg = scale_unit_image(wall_img)
                    rect = wimg.get_rect(center=(cx, cy))
                    screen.blit(wimg, rect)
                else:
                    w = int(HEX_SIZE * 1.1)
                    h = int(HEX_SIZE * 0.6)
                    rect = pygame.Rect(cx - w//2, cy - h//2, w, h)
                    col = (180, 185, 210) if wall.owner == 'ally' else (210, 150, 150)
                    pygame.draw.rect(screen, col, rect, border_radius=4)
                    pygame.draw.rect(screen, (40, 40, 60), rect, 2, border_radius=4)

            # 일반 유닛
            if tile.unit:
                u = tile.unit
                # 전투 중인 병 유닛은 여기서는 그리지 않고, 아래 battles 루프에서 따로 그림
                if u.name == "Soldier" and (q, r) in battle_tiles:
                    if DEBUG_OVERLAY:
                        info = f"{u.health:.0f} HP  ATK:{u.attack:.1f}"
                        t_surf = render_text_cached(font_small, info, (255, 255, 255))
                        screen.blit(t_surf, (cx - t_surf.get_width()//2, cy + HEX_SIZE * 0.2))
                    continue

                # 이미지 우선 렌더
                img = load_unit_image(u.name, u.owner)
                if img:
                    img2 = scale_unit_image(img)
                    rect = img2.get_rect(center=(cx, cy))
                    screen.blit(img2, rect)
                else:
                    # 핀포인트는 색깔 다른 원, 그 외는 기본 원
                    if u.is_pinpoint:
                        col = COLOR_PINPOINT_ALLY if u.owner == 'ally' else COLOR_PINPOINT_ENEMY
                        pygame.draw.circle(screen, col, (cx, cy), HEX_SIZE // 2)
                    else:
                        pygame.draw.circle(screen, COLOR_TEXT, (cx, cy), HEX_SIZE // 3, 2)

                # 디버그 HP/ATK 텍스트
                if DEBUG_OVERLAY:
                    info = f"{u.health:.0f} HP  ATK:{u.attack:.1f}"
                    t_surf = render_text_cached(font_small, info, (255, 255, 255))
                    screen.blit(t_surf, (cx - t_surf.get_width()//2, cy + HEX_SIZE * 0.2))

        # 셋포인트 포격 이펙트
        recent_shots = getattr(game, "recent_shots", [])
        if recent_shots:
            fx = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
            for entry in list(recent_shots):
                t, timer = entry[0], entry[1]
                cx, cy = axial_to_pixel(t.q, t.r, origin=ORIGIN)
                alpha = int(255 * (max(0.0, timer) / 0.5))
                pygame.draw.circle(fx, (255, 60, 60, alpha),
                                   (cx, cy), HEX_SIZE, 3)
            screen.blit(fx, (0, 0))

        # 전투에 참여하지 않는 병 유닛들의 체력바 (단일)
        for (q, r), tile in game.map.tiles.items():
            u = tile.unit
            if not u or u.name != "Soldier":
                continue
            if (q, r) in battle_tiles:
                # 이 타일은 아래의 '전투 중 HP 바/이미지'에서 처리
                continue
            cx, cy = axial_to_pixel(q, r, origin=ORIGIN)
            draw_hp_bar(screen, cx, cy, hp=u.health, max_hp=20, owner=u.owner, dy=0)

        # 전투 중인 병 유닛 둘의 이미지 + HP 바 (위/아래 & 좌/우로 분리)
        for b in battles:
            tile = b["tile"]
            att = b["att"]
            deff = b["def"]
            if tile is None:
                continue

            cx, cy = axial_to_pixel(tile.q, tile.r, origin=ORIGIN)

            # 둘 다 병 유닛인 경우만 그려주자
            units = []
            if att and getattr(att, "name", "") == "Soldier":
                units.append(att)
            if deff and getattr(deff, "name", "") == "Soldier":
                units.append(deff)
            if not units:
                continue

            gap_y = 6   # HP 바 위/아래 간격
            gap_x = HEX_SIZE * 0.4  # 이미지 좌우 간격 (겹치되 조금씩만)

            ally_unit = None
            enemy_unit = None
            for u in units:
                if u.owner == "ally":
                    ally_unit = u
                elif u.owner == "enemy":
                    enemy_unit = u

            # 아군 이미지는 왼쪽, 적군 이미지는 오른쪽(살짝 겹쳐도 됨)
            if ally_unit:
                img = load_unit_image(ally_unit.name, ally_unit.owner)
                if img:
                    img2 = scale_unit_image(img)
                    rect = img2.get_rect(center=(cx - gap_x, cy))
                    screen.blit(img2, rect)
                else:
                    pygame.draw.circle(screen, COLOR_TEXT, (cx - gap_x, cy), HEX_SIZE // 3, 2)

                draw_hp_bar(
                    screen, cx - gap_x * 0.3, cy,   # HP 바는 거의 중앙에 가깝게
                    hp=ally_unit.health, max_hp=20,
                    owner=ally_unit.owner,
                    dy=-gap_y
                )

            if enemy_unit:
                img = load_unit_image(enemy_unit.name, enemy_unit.owner)
                if img:
                    img2 = scale_unit_image(img)
                    rect = img2.get_rect(center=(cx + gap_x, cy))
                    screen.blit(img2, rect)
                else:
                    pygame.draw.circle(screen, COLOR_TEXT, (cx + gap_x, cy), HEX_SIZE // 3, 2)

                draw_hp_bar(
                    screen, cx + gap_x * 0.3, cy,
                    hp=enemy_unit.health, max_hp=20,
                    owner=enemy_unit.owner,
                    dy=+gap_y
                )

        # 전투 타일 표시
        for b in battles:
            t = b["tile"]
            cx, cy = axial_to_pixel(t.q, t.r, origin=ORIGIN)
            pygame.draw.circle(screen, (255, 180, 140),
                               (cx, cy), HEX_SIZE - 4, 3)
            txt = render_text_cached(font_small, "⚔", (255, 200, 170))
            screen.blit(txt, (cx - txt.get_width()//2, cy - HEX_SIZE))

        # 점령 링
        for (q, r), state in capture_states.items():
            cx, cy = axial_to_pixel(q, r, origin=ORIGIN)
            pygame.draw.circle(screen, COLOR_CAPTURE,
                               (cx, cy), HEX_SIZE - 4, 3)
            txt = render_text_cached(font_small,
                                     f"{state['remain']:.1f}s",
                                     COLOR_CAPTURE)
            screen.blit(txt, (cx - txt.get_width() // 2,
                              cy - HEX_SIZE * 1.3))

        # 🔹 벽 파괴 진행 중 링 + 타이머
        for (q, r), state in wall_break_states.items():
            tile = game.map.get_tile(q, r)
            if not tile:
                continue
            cx, cy = axial_to_pixel(q, r, origin=ORIGIN)
            pygame.draw.circle(screen, COLOR_WALL_BREAK,
                               (cx, cy), HEX_SIZE - 8, 2)
            txt = render_text_cached(font_small,
                                     f"{state['remain']:.1f}s",
                                     COLOR_WALL_BREAK)
            screen.blit(txt, (cx - txt.get_width() // 2,
                              cy + HEX_SIZE * 0.2))

        if hover:
            cx, cy = axial_to_pixel(hover.q, hover.r, origin=ORIGIN)
            pygame.draw.polygon(screen, COLOR_HL,
                                hex_polygon(cx, cy, HEX_SIZE - 1), 2)
        if selected_unit_tile:
            cx, cy = axial_to_pixel(selected_unit_tile.q,
                                    selected_unit_tile.r,
                                    origin=ORIGIN)
            pygame.draw.polygon(screen, COLOR_OK,
                                hex_polygon(cx, cy, HEX_SIZE - 3), 3)

        # 데미지 팝업
        for (x, y, text, color, life, vy, total) in damage_popups:
            alpha = max(0, min(255, int(255 * (life / total))))
            base_font = popup_font
            blit_text_outline(
                screen, text, base_font,
                int(x - base_font.size(text)[0] / 2),
                int(y - base_font.get_height() / 2),
                inner_color=color, outline_color=(0, 0, 0),
                outline_w=2, alpha=alpha,
            )

        # 버튼/UI
        hud_hover = pygame.Rect(hud_btn_rect).collidepoint(mouse_pos)
        draw_button(screen, hud_btn_rect,
                    "👁  HUD" if hud_visible else "👁  SHOW",
                    font_small, hovered=hud_hover)
        fs_hover = pygame.Rect(fs_btn_rect).collidepoint(mouse_pos)
        draw_button(screen, fs_btn_rect,
                    "⛶  FULL" if not is_fullscreen else "⛶  WINDOW",
                    font_small, hovered=fs_hover)

        # HUD
        check_hud_dirty()
        if hud_visible:
            if hud_dirty or hud_surface is None:
                build_hud_surface()
            screen.blit(hud_surface, (12, 60))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

# --------------------------------------------------------------------
# 서버에서 사용하는 클래스 임포트 (역직렬화용)
# --------------------------------------------------------------------
try:
    from game.game_logic import Game
    from game.unit import Unit
    from game.tile import Tile
    from game.player import Player
    from game.hex_map import HexMap
except ImportError as e:
    print(f"게임 모듈 임포트 실패: {e}")
    sys.exit(1)

# --------------------------------------------------------------------
# 상수 (서버와 동일)
# --------------------------------------------------------------------
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 12345
BUFFER_SIZE = 4096

# --------------------------------------------------------------------
# 유틸리티 함수 (서버와 동일)
# --------------------------------------------------------------------
# (서버의 send_data, receive_data 함수를 여기에 복사/붙여넣기)

def send_data(conn: socket.socket, data: any):
    """pickle을 사용하여 데이터를 전송합니다. (서버와 동일)"""
    # ... (서버 코드의 send_data 구현) ...
    try:
        serialized_data = pickle.dumps(data)
        data_len = len(serialized_data)
        conn.sendall(data_len.to_bytes(4, 'big'))
        conn.sendall(serialized_data)
    except (socket.error, pickle.PickleError):
        raise

def receive_data(conn: socket.socket) -> any:
    """pickle을 사용하여 데이터를 수신합니다. (서버와 동일)"""
    # ... (서버 코드의 receive_data 구현) ...
    try:
        len_bytes = conn.recv(4)
        if not len_bytes: return None
        data_len = int.from_bytes(len_bytes, 'big')
        
        data_buffer = b''
        while len(data_buffer) < data_len:
            chunk = conn.recv(min(data_len - len(data_buffer), BUFFER_SIZE))
            if not chunk: raise EOFError
            data_buffer += chunk
            
        return pickle.loads(data_buffer)
    except Exception:
        return None

# --------------------------------------------------------------------
# 클라이언트 메인 루프
# --------------------------------------------------------------------
# visual_main.py의 Pygame 초기화 코드를 가져와서 사용해야 합니다.

class GameClient:
    def __init__(self):
        # ⚠️ visual_main.py의 초기화 코드를 여기에 사용합니다.
        pygame.init()
        # LOGICAL_W, LOGICAL_H, screen, clock 등의 변수는 visual_main.py 복사본에서 가져옵니다.
        # ... (visual_main.py의 Pygame 전역 변수 초기화) ...
        
        self.game = None # 서버로부터 수신할 게임 상태
        self.my_role = None # 'server' 또는 'client' (P1/P2 구분용)
        self.conn = None
        self.running = True
        
        # visual_main.py의 전역 상태 변수들을 여기에 옮겨야 합니다.
        self.selected_tile = None
        self.selected_unit_tile = None
        self.hud_visible = True
        self.is_fullscreen = False
        self.damage_popups = [] # 시각 효과는 클라이언트에서 독립적으로 처리

    def connect(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.conn.connect((SERVER_HOST, SERVER_PORT))
            initial_data = receive_data(self.conn)
            if initial_data and initial_data.get('id'):
                self.my_role = initial_data['id']
                print(f"✅ 서버 접속 성공. 내 역할: {self.my_role}")
                threading.Thread(target=self.receive_data_loop, daemon=True).start()
                return True
        except socket.error as e:
            print(f"❌ 서버 접속 실패: {e}")
            self.running = False
            return False

    def receive_data_loop(self):
        while self.running:
            try:
                new_game_state = receive_data(self.conn)
                if new_game_state is None: break
                self.game = new_game_state # 서버가 이미 시점을 바꿔서 보낸 상태
                
            except Exception:
                break
        self.running = False

    def send_command(self, action: str, params: dict = {}):
        """서버로 액션을 전송합니다."""
        command = {'action': action, 'params': params}
        try:
            send_data(self.conn, command)
        except Exception as e:
            print(f"커맨드 전송 실패: {e}")
            self.running = False
            
    # ------------------------------------------------------------
    # ⚠️ handle_events(이벤트 처리) 함수 수정
    # ------------------------------------------------------------
    # visual_main.py의 handle_events 함수를 가져와서, 
    # 게임 상태를 변경하는 모든 호출을 self.send_command(...)로 대체해야 합니다.
    # 예시: 유닛 구매, 배치, 이동, 셋포인트 발사 등.
    def handle_input(self, mouse_pos):
        # ... (visual_main.py의 handle_events 함수 내용 복사) ...
        # (마우스 클릭 처리 부분에서)
        # 📌 기존: game.players['ally'].purchase_unit('soldier')
        # 📌 변경: self.send_command('purchase_unit', {'unit_type': 'soldier'})
        
        # 📌 기존: tile.place_unit(unit_to_place)
        # 📌 변경: self.send_command('place_unit', {'unit_name': unit_to_place.name, 'q': tile.q, 'r': tile.r})
        
        # 📌 기존: game.move_unit(...)
        # 📌 변경: self.send_command('move_unit', {'from_q': q1, 'from_r': r1, 'to_q': q2, 'to_r': r2})
        
        pass # 실제 구현은 visual_main.py의 로직을 따라야 함.

    # ------------------------------------------------------------
    # draw_game_state (그리기) 함수 수정 (준비 시간 표시 추가)
    # ------------------------------------------------------------
    # visual_main.py의 draw_game_state 함수를 가져와서 사용
    # 특히, 준비 시간이 남았을 경우 화면에 시간을 표시하는 로직을 추가합니다.

    def run(self):
        if not self.connect():
            return

        print("게임 클라이언트 루프 시작.")
        while self.running:
            # clock, FPS는 visual_main.py에서 정의된 것을 사용해야 합니다.
            # 여기서는 편의상 전역 변수를 가정합니다.
            dt = self.clock.tick(FPS) / 1000.0 

            mouse_pos = pygame.mouse.get_pos()

            # 1. 입력 처리 (서버로 커맨드 전송)
            self.handle_input(mouse_pos)
            
            # 2. 게임 로직 업데이트는 서버가 담당. 클라이언트는 시각 효과만 업데이트
            # ⚠️ game.update_systems(dt) 호출 삭제!
            # visual_main.py의 데미지 팝업, 폭발 효과 등만 업데이트합니다.
            
            # 3. 화면 그리기
            # draw_game_state(self.screen, self.game, self.selected_tile, ...)
            # (visual_main.py의 그리기 함수 호출)
            if self.game:
                # 📌 준비 시간 표시 (추가 요구사항)
                if self.game.game_phase == 'preparation':
                    time_str = f"준비 시간: {int(self.game.time_remaining // 60):02d}:{int(self.game.time_remaining % 60):02d}"
                    # 폰트, 화면에 time_str 출력 로직 추가
                    # ... 
                
                # 📌 게임 오버 표시
                if self.game.game_phase == 'game_over':
                    winner_role = '나' if self.game.winner == self.my_role else '적군'
                    message = f"게임 종료! 승리: {winner_role}"
                    # ... (화면에 메시지 출력) ...
                    
            pygame.display.flip()

        if self.conn:
            self.conn.close()
        pygame.quit()
        sys.exit()

if __name__ == '__main__':
    # ⚠️ 클라이언트는 최소 두 개의 터미널에서 실행해야 합니다.
    # 하나는 서버(server.py)를, 다른 두 개는 클라이언트(client.py)를 실행합니다.
    client = GameClient()
    client.run()
