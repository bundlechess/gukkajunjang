import pygame
import sys
import math
import socket
import threading
import pickle
import time

# --------------------------------------------------------------------
# [설정] visual_main.py의 상수 및 설정 복원
# --------------------------------------------------------------------
LOGICAL_W, LOGICAL_H = 1280, 720
FPS = 60
HEX_SIZE = 28
SERVER_IP = '127.0.0.1' # 테스트 시 로컬 IP
SERVER_PORT = 12345
BUFFER_SIZE = 16384

# 색상
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

# --------------------------------------------------------------------
# [클라이언트] 네트워크 및 메인 클래스
# --------------------------------------------------------------------
class GameClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.RESIZABLE | pygame.SCALED)
        pygame.display.set_caption("Hex War Multiplayer")
        self.clock = pygame.time.Clock()
        
        # 폰트 초기화
        self.font = pygame.font.SysFont("malgungothic", 20)
        self.font_s = pygame.font.SysFont("malgungothic", 16)
        self.font_l = pygame.font.SysFont("malgungothic", 40, bold=True)
        
        # 상태
        self.game = None
        self.running = True
        self.socket = None
        self.my_role = None # 'ally' (서버가 시점을 바꿔주므로 항상 ally로 인식)

        # UI State
        self.selected_tile = None
        self.selected_unit_tile = None
        self.damage_popups = [] # [x, y, text, color, life, vy, total]
        self.hud_visible = True
        self.is_fullscreen = False

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((SERVER_IP, SERVER_PORT))
            
            # 초기 데이터(역할) 수신
            init_packet = self._recv_once()
            if init_packet:
                print(f"서버 연결 성공: {init_packet}")
                # 서버가 'server'든 'client'든 화면은 'ally' 기준으로 오므로
                # 내부 로직은 'ally'로 고정
                self.my_role = 'ally'
            
            # 수신 스레드
            threading.Thread(target=self.recv_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"접속 실패: {e}")
            return False

    def _recv_once(self):
        try:
            len_bytes = self.socket.recv(4)
            if not len_bytes: return None
            length = int.from_bytes(len_bytes, 'big')
            buf = b''
            while len(buf) < length:
                chunk = self.socket.recv(min(length - len(buf), BUFFER_SIZE))
                if not chunk: return None
                buf += chunk
            return pickle.loads(buf)
        except:
            return None

    def recv_loop(self):
        while self.running:
            data = self._recv_once()
            if data is None:
                self.running = False
                break
            # 게임 상태 덮어쓰기
            if hasattr(data, 'map'): # Game 객체인지 확인
                self.game = data

    def send_cmd(self, action, params={}):
        if not self.socket: return
        try:
            payload = pickle.dumps({'action': action, 'params': params})
            self.socket.sendall(len(payload).to_bytes(4, 'big'))
            self.socket.sendall(payload)
        except:
            self.running = False

    # ----------------------------------------------------------------
    # 입력 처리 (로직 제거 -> 서버 전송)
    # ----------------------------------------------------------------
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left Click
                    self.on_click(mouse_pos)
                elif event.button == 3: # Right Click
                    self.selected_tile = None
                    self.selected_unit_tile = None

    def on_click(self, pos):
        if not self.game: return
        
        # 1. UI 버튼 (Full Screen / HUD)
        # (간단히 좌표 하드코딩 - visual_main UI 위치 참고)
        if 20 <= pos[0] <= 120 and LOGICAL_H - 60 <= pos[1] <= LOGICAL_H - 20:
            self.hud_visible = not self.hud_visible
            return
        
        # 2. 상점 구매 (HUD가 보일 때)
        if self.hud_visible and pos[0] > LOGICAL_W - 240:
            # y좌표에 따라 유닛 구매
            y = pos[1]
            u_type = None
            if 60 <= y < 110: u_type = 'soldier'
            elif 120 <= y < 170: u_type = 'setpoint'
            elif 180 <= y < 230: u_type = 'medical'
            elif 240 <= y < 290: u_type = 'wall'
            
            if u_type:
                self.send_cmd('purchase_unit', {'unit_type': u_type})
            return

        # 3. 맵 상호작용
        # 중앙 정렬 오프셋 계산
        map_w = (self.game.map.size * 2 + 1) * HEX_SIZE * math.sqrt(3)
        map_h = (self.game.map.size * 2 + 1) * HEX_SIZE * 1.5
        ox = (LOGICAL_W - map_w) // 2
        oy = (LOGICAL_H - map_h) // 2
        
        q, r = pixel_to_hex(pos[0] - ox, pos[1] - oy, HEX_SIZE)
        tile = self.game.map.get_tile(q, r)
        
        if not tile: return
        
        me = self.game.players['ally']
        
        # (A) 유닛 배치 (인벤토리에 유닛이 있고, 내 땅일 때)
        if me.units_inventory and tile.owner == 'ally':
            # 유닛이 비었거나(일반), 벽이 없거나(벽유닛)
            unit_to_place = me.units_inventory[0]
            can_place = False
            if unit_to_place.is_wall:
                if tile.wall is None: can_place = True
            else:
                if tile.unit is None: can_place = True
                
            if can_place:
                self.send_cmd('place_unit', {
                    'unit_name': unit_to_place.name,
                    'q': q, 'r': r
                })
                return

        # (B) 유닛 선택 및 이동/공격
        if self.selected_unit_tile:
            # 이미 선택된 유닛이 있을 때 -> 행동
            su = self.selected_unit_tile.unit
            if su:
                if su.is_setpoint: # 포격
                    self.send_cmd('setpoint_fire', {
                        'fire_q': self.selected_unit_tile.q, 'fire_r': self.selected_unit_tile.r,
                        'target_q': q, 'target_r': r
                    })
                else: # 이동
                    self.send_cmd('move_unit', {
                        'from_q': self.selected_unit_tile.q, 'from_r': self.selected_unit_tile.r,
                        'to_q': q, 'to_r': r
                    })
            self.selected_unit_tile = None
            self.selected_tile = None
        else:
            # 선택
            if tile.unit and tile.unit.owner == 'ally':
                self.selected_unit_tile = tile
                self.selected_tile = tile
            else:
                self.selected_tile = tile

    # ----------------------------------------------------------------
    # 그리기 및 메인 루프
    # ----------------------------------------------------------------
    def run(self):
        if not self.connect(): return
        
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            
            self.handle_input()
            
            self.screen.fill(COLOR_BG)
            
            if self.game:
                # 맵 그리기
                self.draw_game(dt)
                
                # UI 그리기
                if self.hud_visible:
                    self.draw_hud()
                
                # 정보 텍스트 (준비 시간 / 승패)
                self.draw_info_overlay()
            else:
                txt = self.font.render("Connecting to Server...", True, COLOR_TEXT)
                self.screen.blit(txt, (LOGICAL_W//2 - 100, LOGICAL_H//2))
            
            pygame.display.flip()
        
        if self.socket: self.socket.close()
        pygame.quit()
        sys.exit()

    def draw_game(self, dt):
        # 오프셋
        map_w = (self.game.map.size * 2 + 1) * HEX_SIZE * math.sqrt(3)
        map_h = (self.game.map.size * 2 + 1) * HEX_SIZE * 1.5
        ox = (LOGICAL_W - map_w) // 2
        oy = (LOGICAL_H - map_h) // 2
        
        # 타일 그리기
        for tile in self.game.map.tiles.values():
            cx, cy = hex_to_pixel(tile.q, tile.r, HEX_SIZE)
            cx, cy = cx + ox, cy + oy
            
            # 색상
            color = COLOR_GRID
            if tile.terrain == 'gold': color = COLOR_GOLD
            elif tile.owner == 'ally': color = COLOR_ALLY
            elif tile.owner == 'enemy': color = COLOR_ENEMY
            
            # 약간 어둡게 베이스
            r, g, b = color
            base_col = (max(0, r-40), max(0, g-40), max(0, b-40))
            if tile.boundary: base_col = COLOR_BOUNDARY
            
            poly = hex_polygon(cx, cy, HEX_SIZE-1)
            pygame.draw.polygon(self.screen, base_col, poly)
            pygame.draw.polygon(self.screen, (50,50,50), poly, 1)
            
            # 유닛 그리기
            units = []
            if tile.wall: units.append(tile.wall)
            if tile.unit: units.append(tile.unit)
            
            for u in units:
                ucol = COLOR_ALLY if u.owner == 'ally' else COLOR_ENEMY
                if u.is_pinpoint: ucol = COLOR_PINPOINT_ALLY if u.owner == 'ally' else COLOR_PINPOINT_ENEMY
                
                if u.is_wall:
                    rr = HEX_SIZE
                    pygame.draw.rect(self.screen, (100,100,100), (cx-rr/2, cy-rr/2, rr, rr))
                    pygame.draw.rect(self.screen, ucol, (cx-rr/2, cy-rr/2, rr, rr), 3)
                else:
                    rad = HEX_SIZE * 0.6
                    pygame.draw.circle(self.screen, ucol, (cx, cy), rad)
                    # 약자
                    nm = u.name[0]
                    if u.name=="Medical": nm="+"
                    nt = self.font_s.render(nm, True, (255,255,255))
                    self.screen.blit(nt, (cx-nt.get_width()/2, cy-nt.get_height()/2))
                    
                # HP Bar
                if not u.is_wall:
                    draw_hp_bar(self.screen, cx-15, cy-HEX_SIZE+5, u.health, 100 if u.is_pinpoint else 20)

        # 하이라이트
        if self.selected_tile:
            cx, cy = hex_to_pixel(self.selected_tile.q, self.selected_tile.r, HEX_SIZE)
            pygame.draw.polygon(self.screen, (255,255,255), hex_polygon(cx+ox, cy+oy, HEX_SIZE-2), 2)
        if self.selected_unit_tile:
            cx, cy = hex_to_pixel(self.selected_unit_tile.q, self.selected_unit_tile.r, HEX_SIZE)
            pygame.draw.polygon(self.screen, (0,255,0), hex_polygon(cx+ox, cy+oy, HEX_SIZE+2), 3)

    def draw_hud(self):
        # 배경 패널
        s = pygame.Surface((240, LOGICAL_H), pygame.SRCALPHA)
        s.fill(COLOR_PANEL)
        self.screen.blit(s, (LOGICAL_W-240, 0))
        
        # 정보
        p = self.game.players['ally']
        info = [
            f"Money: {p.money}",
            f"Units: {len(p.units_inventory)}"
        ]
        for i, txt in enumerate(info):
            t = self.font.render(txt, True, COLOR_TEXT)
            self.screen.blit(t, (LOGICAL_W-220, 20 + i*30))
            
        # 상점 버튼 (단순화)
        items = [
            ("Soldier ($100)", 60),
            ("Setpoint ($500)", 120),
            ("Medical ($1000)", 180),
            ("Wall ($50)", 240)
        ]
        for text, y in items:
            rect = (LOGICAL_W-230, y, 220, 40)
            pygame.draw.rect(self.screen, COLOR_BUTTON, rect)
            pygame.draw.rect(self.screen, (100,100,100), rect, 1)
            ts = self.font_s.render(text, True, COLOR_TEXT)
            self.screen.blit(ts, (rect[0]+10, rect[1]+10))
            
        # 하단 버튼
        pygame.draw.rect(self.screen, COLOR_BUTTON, (20, LOGICAL_H-60, 100, 40))
        h_txt = self.font.render("HUD", True, COLOR_TEXT)
        self.screen.blit(h_txt, (40, LOGICAL_H-55))

    def draw_info_overlay(self):
        # 준비 시간
        if self.game.game_phase == 'preparation':
            remain = int(self.game.time_remaining)
            txt = f"준비 시간: {remain//60}:{remain%60:02d}"
            ts = self.font_l.render(txt, True, (255, 255, 0))
            self.screen.blit(ts, (LOGICAL_W//2 - ts.get_width()//2, 50))
            
        # 승리/패배
        if self.game.game_phase == 'game_over':
            winner = self.game.winner
            # my_role은 항상 ally (서버가 바꿔줌) -> winner가 'ally'인지 'client'(상대)인지 체크
            # 하지만 check_win에서 winner를 'server'/'client'로 설정함.
            # 클라 입장에서: 내가 server역할이면 'server'승이 내 승리.
            #              내가 client역할이면 'client'승이 내 승리.
            
            # 접속 시 받은 메시지가 없어서 정확한 role 파악이 힘들다면, 
            # 단순히 핀포인트 파괴 여부로 화면에 표시하는 게 낫지만,
            # 여기선 간단히 텍스트만 출력
            res_txt = f"WINNER: {winner.upper()}"
            ts = self.font_l.render(res_txt, True, (0, 255, 0))
            self.screen.blit(ts, (LOGICAL_W//2 - ts.get_width()//2, LOGICAL_H//2))


# --------------------------------------------------------------------
# 헬퍼 함수 (Visual Main 로직 복원)
# --------------------------------------------------------------------
def pixel_to_hex(x, y, size):
    q = (2./3 * x) / size
    r = (-1./3 * x + math.sqrt(3)/3 * y) / size
    return round_hex(q, r)

def hex_to_pixel(q, r, size):
    x = size * 1.5 * q
    y = size * math.sqrt(3) * (r + q / 2.0)
    return x, y

def round_hex(q, r):
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    q_diff, r_diff, s_diff = abs(rq - q), abs(rr - r), abs(rs - s)
    if q_diff > r_diff and q_diff > s_diff:
        rq = -rr - rs
    elif r_diff > s_diff:
        rr = -rq - rs
    return int(rq), int(rr)

def hex_polygon(x, y, size):
    pts = []
    for i in range(6):
        deg = 60 * i
        rad = math.pi / 180 * deg
        pts.append((x + size * math.cos(rad), y + size * math.sin(rad)))
    return pts

def draw_hp_bar(screen, x, y, hp, max_hp):
    pct = max(0, min(1, hp / max_hp))
    w, h = 30, 4
    pygame.draw.rect(screen, (0,0,0), (x, y, w, h))
    pygame.draw.rect(screen, (0,255,0), (x, y, w*pct, h))

if __name__ == "__main__":
    GameClient().run()
