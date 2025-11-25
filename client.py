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
# ... (visual_main.py의 내용을 여기에 붙여넣기) ...
# ... (draw_game_state 함수까지 포함) ...

# ==================================================================================
# 아래부터는 멀티플레이 전용 클라이언트 로직입니다.
# visual_main.py의 하단 'def main(): ...' 부분을 아래 코드로 대체한다고 생각하면 됩니다.
# ==================================================================================

SERVER_IP = '127.0.0.1' # 서버 IP (로컬 테스트용)
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
