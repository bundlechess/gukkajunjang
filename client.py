import pygame
import sys
import socket
import threading
import pickle
import math # visual_main의 의존성

# ==================================================================================
# [중요] 여기에 visual_main.py의 상단 부분(상수, 색상, Helper 함수, 그리기 함수 등)을
# 그대로 복사해서 붙여넣으세요.
# 'Game' 클래스 import 부분부터 'draw_game_state' 함수 끝까지 전부 필요합니다.
# ==================================================================================
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


# ==================================================================================
# 아래부터는 멀티플레이 전용 클라이언트 로직입니다.
# visual_main.py의 하단 'def main(): ...' 부분을 아래 코드로 대체한다고 생각하면 됩니다.
# ==================================================================================

SERVER_IP = '172.16.200.206' # 서버 IP (로컬 테스트용)
SERVER_PORT = 12345
BUFFER_SIZE = 4096

class GameClient:
    def __init__(self):
        pygame.init()
        # visual_main.py에 있는 상수 사용
        self.screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.RESIZABLE | pygame.SCALED)
        pygame.display.set_caption("1v1 Multiplayer Client")
        self.clock = pygame.time.Clock()

        # 게임 상태 (서버에서 받음)
        self.game = None
        self.my_role = None  # 'ally' (무조건 서버가 시점을 변환해서 보내줌)
        
        # UI 상태
        self.selected_tile = None
        self.selected_unit_tile = None
        self.hud_visible = True
        self.is_fullscreen = False
        self.damage_popups = [] 

        # 네트워크
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = True

    def connect_to_server(self):
        try:
            self.client_socket.connect((SERVER_IP, SERVER_PORT))
            print(f"서버({SERVER_IP}:{SERVER_PORT})에 접속했습니다.")
            
            # 1. 초기 접속 메시지 수신 (ID 할당 등)
            init_data = self.receive_data()
            if init_data:
                print(f"서버 메시지: {init_data}")
                # 서버가 시점을 바꿔주므로 클라이언트는 항상 자신이 'ally'라고 생각하고 렌더링하면 됨
                self.my_role = 'ally' 

            # 2. 데이터 수신 스레드 시작
            threading.Thread(target=self.network_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"서버 접속 실패: {e}")
            return False

    def receive_data(self):
        """서버로부터 pickle 데이터 수신"""
        try:
            len_bytes = self.client_socket.recv(4)
            if not len_bytes: return None
            data_len = int.from_bytes(len_bytes, 'big')
            
            data_buffer = b''
            while len(data_buffer) < data_len:
                chunk = self.client_socket.recv(min(data_len - len(data_buffer), BUFFER_SIZE))
                if not chunk: return None
                data_buffer += chunk
            return pickle.loads(data_buffer)
        except Exception:
            return None

    def send_command(self, action, params=None):
        """서버로 행동 요청 전송"""
        if params is None: params = {}
        payload = {'action': action, 'params': params}
        try:
            data = pickle.dumps(payload)
            length = len(data)
            self.client_socket.sendall(length.to_bytes(4, 'big'))
            self.client_socket.sendall(data)
        except Exception as e:
            print(f"전송 실패: {e}")

    def network_loop(self):
        """서버에서 오는 게임 상태를 계속 받아서 self.game 갱신"""
        while self.running:
            data = self.receive_data()
            if data is None:
                print("서버와 연결이 끊어졌습니다.")
                self.running = False
                break
            
            # 서버가 보내준 Game 객체를 통째로 덮어씌움
            # (서버가 이미 fog of war 처리를 해서 보냄)
            self.game = data

    def handle_input(self):
        # 마우스 좌표 변환 (스케일링 고려)
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # 좌클릭
                    self.on_left_click(mouse_pos)
                elif event.button == 3: # 우클릭
                    self.on_right_click(mouse_pos)

    def on_left_click(self, mouse_pos):
        if not self.game: return

        # 1. UI 버튼 처리 (HUD, Fullscreen 등은 로컬에서 처리해도 무방하거나, 서버 로직과 무관)
        # (visual_main.py의 UI 좌표 상수 사용)
        hud_btn_rect = (20, LOGICAL_H - 60, 100, 40)
        fs_btn_rect = (130, LOGICAL_H - 60, 120, 40)
        
        if pygame.Rect(hud_btn_rect).collidepoint(mouse_pos):
            self.hud_visible = not self.hud_visible
            return
        if pygame.Rect(fs_btn_rect).collidepoint(mouse_pos):
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                self.screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.FULLSCREEN | pygame.SCALED)
            else:
                self.screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.RESIZABLE | pygame.SCALED)
            return

        # 2. 게임 내 상호작용 (유닛 구매 등)
        # 상점 UI 영역 클릭 확인
        # (visual_main.py의 draw_hud 로직 참고하여 영역 계산 필요하지만, 여기서는 간략화)
        if self.hud_visible:
            # 예: 상점 버튼 클릭 시 서버로 구매 요청
            # visual_main.py의 UI 배치를 참고하여 클릭 영역 하드코딩 혹은 계산
            panel_x = LOGICAL_W - 220
            
            # 병사 구매 (y=60 근처)
            if pygame.Rect(panel_x + 10, 60, 200, 50).collidepoint(mouse_pos):
                self.send_command('purchase_unit', {'unit_type': 'soldier'})
                return
            # 셋포인트 구매 (y=120 근처)
            elif pygame.Rect(panel_x + 10, 120, 200, 50).collidepoint(mouse_pos):
                self.send_command('purchase_unit', {'unit_type': 'setpoint'})
                return
            # 보건소 구매 (y=180 근처)
            elif pygame.Rect(panel_x + 10, 180, 200, 50).collidepoint(mouse_pos):
                self.send_command('purchase_unit', {'unit_type': 'medical'})
                return
             # 벽 구매 (y=240 근처 - visual_main.py에 있다면)
            elif pygame.Rect(panel_x + 10, 240, 200, 50).collidepoint(mouse_pos):
                self.send_command('purchase_unit', {'unit_type': 'wall'})
                return

        # 3. 맵 타일 클릭
        # 헥사곤 좌표 변환 (visual_main.py의 pixel_to_hex 사용)
        mx, my = mouse_pos
        # 중앙 정렬 오프셋 적용 (visual_main.py와 동일해야 함)
        map_pixel_width = (self.game.map.size * 2 + 1) * HEX_SIZE * math.sqrt(3)
        map_pixel_height = (self.game.map.size * 2 + 1) * HEX_SIZE * 1.5
        offset_x = (LOGICAL_W - map_pixel_width) // 2
        offset_y = (LOGICAL_H - map_pixel_height) // 2
        
        q, r = pixel_to_hex(mx - offset_x, my - offset_y, HEX_SIZE) # visual_main의 함수
        tile = self.game.map.get_tile(q, r)
        
        if tile:
            self.handle_tile_interaction(tile)

    def handle_tile_interaction(self, tile):
        # 내 플레이어 객체 (서버가 보내준 view에서는 항상 'ally')
        me = self.game.players['ally']
        
        # A. 유닛 배치 (인벤토리에 유닛이 있고, 클릭한 타일이 내 땅일 때)
        # 가장 최근에 산 유닛을 배치한다고 가정
        if me.units_inventory:
            unit_to_place = me.units_inventory[0] # 인벤토리 첫번째 유닛
            # 서버로 배치 요청
            self.send_command('place_unit', {
                'unit_name': unit_to_place.name, # 식별용
                'q': tile.q, 
                'r': tile.r
            })
            # 클라이언트는 예측해서 그리지 않고, 서버 응답(다음 프레임)을 기다림
            return

        # B. 유닛 선택 및 이동/공격 준비
        if self.selected_unit_tile:
            # 이미 유닛을 선택한 상태에서 다른 타일 클릭 -> 이동 또는 공격 시도
            
            # 셋포인트 발사 시도
            unit = self.selected_unit_tile.unit
            if unit and unit.is_setpoint:
                self.send_command('setpoint_fire', {
                    'fire_q': self.selected_unit_tile.q,
                    'fire_r': self.selected_unit_tile.r,
                    'target_q': tile.q,
                    'target_r': tile.r
                })
                self.selected_unit_tile = None
                return

            # 일반 이동 시도
            self.send_command('move_unit', {
                'from_q': self.selected_unit_tile.q,
                'from_r': self.selected_unit_tile.r,
                'to_q': tile.q,
                'to_r': tile.r
            })
            self.selected_unit_tile = None
            self.selected_tile = None
            
        else:
            # 유닛 선택
            if tile.unit and tile.unit.owner == 'ally':
                self.selected_unit_tile = tile
                self.selected_tile = tile
            else:
                self.selected_tile = tile

    def on_right_click(self, mouse_pos):
        # 우클릭 시 선택 취소
        self.selected_tile = None
        self.selected_unit_tile = None

    def run(self):
        if not self.connect_to_server():
            return

        while self.running:
            # 1. 입력 처리
            self.handle_input()
            
            # 2. 로직 업데이트 (클라이언트는 시각 효과만 업데이트)
            # self.game.update_systems(dt)  <-- [삭제!] 절대 호출 금지
            dt = self.clock.tick(FPS) / 1000.0
            
            # 3. 그리기
            self.screen.fill(COLOR_BG)
            
            if self.game:
                # visual_main.py의 그리기 함수 호출
                # 주의: HUD를 그릴 때 draw_hud 함수가 game 객체를 필요로 함
                draw_game_state(self.screen, self.game, self.selected_tile, 
                                self.selected_unit_tile, self.damage_popups, dt)
                
                # 준비 시간 텍스트 표시 (서버에서 시간 정보를 받아옴)
                if getattr(self.game, 'game_phase', '') == 'preparation':
                    time_left = getattr(self.game, 'time_remaining', 0)
                    font_timer = pygame.font.SysFont("malgungothic", 40, bold=True)
                    timer_text = f"준비 시간: {int(time_left // 60)}:{int(time_left % 60):02d}"
                    text_surf = font_timer.render(timer_text, True, (255, 255, 0))
                    self.screen.blit(text_surf, (LOGICAL_W // 2 - text_surf.get_width() // 2, 50))
                
                # 승리/패배 메시지
                if getattr(self.game, 'winner', None):
                    result = "승리!" if self.game.winner == self.my_role else "패배..."
                    font_res = pygame.font.SysFont("malgungothic", 80, bold=True)
                    color = (100, 255, 100) if self.game.winner == self.my_role else (255, 100, 100)
                    res_surf = font_res.render(result, True, color)
                    self.screen.blit(res_surf, (LOGICAL_W//2 - res_surf.get_width()//2, LOGICAL_H//2))

            else:
                # 게임 데이터 수신 전 대기 화면
                font = pygame.font.SysFont("arial", 30)
                text = font.render("Connecting to server...", True, (255, 255, 255))
                self.screen.blit(text, (LOGICAL_W//2 - 100, LOGICAL_H//2))

            pygame.display.flip()

        self.client_socket.close()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    client = GameClient()
    client.run()
