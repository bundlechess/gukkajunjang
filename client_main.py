# client_main.py
import socket
import threading
from typing import Dict, Any, Tuple

import pygame
import math

from net_common import send_json, recv_json

SERVER_IP = "127.0.0.1"   # 같은 PC면 그대로
SERVER_PORT = 50000

LOGICAL_W, LOGICAL_H = 1280, 720
HEX_SIZE = 28
SQRT3 = math.sqrt(3)
ORIGIN = (LOGICAL_W // 2, LOGICAL_H // 2 + 20)

COLOR_BG = (35, 36, 40)
COLOR_GRID = (92, 96, 105)
COLOR_ALLY = (110, 170, 255)
COLOR_ENEMY = (255, 130, 130)
COLOR_HL = (255, 255, 0)
COLOR_TEXT = (235, 238, 242)
COLOR_CAPTURE = (255, 230, 120)
COLOR_PINPOINT_ALLY = (20, 120, 255)
COLOR_PINPOINT_ENEMY = (255, 80, 80)
COLOR_BATTLE_RING = (255, 180, 140)

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


server_state: Dict[str, Any] = {}
my_side: str = "ally"
running = True

def net_thread_main(sock: socket.socket):
    global server_state, my_side, running
    try:
        while True:
            data = recv_json(sock)
            if data is None:
                print("[CLIENT] 서버 끊김")
                running = False
                break
            if data.get("type") == "hello":
                my_side = data.get("side", "ally")
                print("[CLIENT] 나의 진영:", my_side)
            elif data.get("type") == "state":
                server_state = data.get("state", {})
    except Exception as e:
        print("[CLIENT] 네트워크 예외:", e)
    finally:
        running = False
        try:
            sock.close()
        except:
            pass


def nearest_tile_from_pos(mouse_pos) -> Tuple[int, int] | None:
    if "tiles" not in server_state:
        return None
    mx, my = mouse_pos
    best = None
    best_d2 = 10**18
    for t in server_state["tiles"]:
        cx, cy = axial_to_pixel(t["q"], t["r"])
        d2 = (mx - cx)**2 + (my - cy)**2
        if d2 < best_d2:
            best_d2 = d2
            best = (t["q"], t["r"])
    return best


def main():
    global running

    # 서버 접속
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))
    print("[CLIENT] 서버 접속:", SERVER_IP, SERVER_PORT)

    threading.Thread(target=net_thread_main, args=(sock,), daemon=True).start()

    pygame.init()
    pygame.display.set_caption("국가전쟁 멀티 클라이언트")
    screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.SCALED)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("malgungothic", 20)
    font_small = pygame.font.SysFont("malgungothic", 16)

    selected_type = "soldier"
    selected_tile: Tuple[int, int] | None = None

    while running:
        dt = clock.tick(45) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        # 입력
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    selected_type = "soldier"
                elif event.key == pygame.K_2:
                    selected_type = "setpoint"
                elif event.key == pygame.K_3:
                    selected_type = "medical"

            elif event.type == pygame.MOUSEBUTTONDOWN:
                tile_coord = nearest_tile_from_pos(mouse_pos)
                if tile_coord is None:
                    continue
                tq, tr = tile_coord

                # 좌클릭: 병 선택 / 이동
                if event.button == 1:
                    tile_info = None
                    for t in server_state.get("tiles", []):
                        if t["q"] == tq and t["r"] == tr:
                            tile_info = t
                            break
                    if tile_info is None:
                        continue
                    u = tile_info.get("unit")

                    if u and u["owner"] == my_side and u["name"] == "Soldier":
                        # 병 선택
                        selected_tile = (tq, tr)
                    elif selected_tile is not None:
                        from_q, from_r = selected_tile
                        cmd = {
                            "kind": "move",
                            "from": [from_q, from_r],
                            "to": [tq, tr],
                        }
                        send_json(sock, {"type": "input", "cmd": cmd})
                        selected_tile = None

                # 우클릭: 현재 선택된 타입 배치
                elif event.button == 3:
                    cmd = {
                        "kind": "place",
                        "unit_type": selected_type,
                        "q": tq,
                        "r": tr,
                    }
                    send_json(sock, {"type": "input", "cmd": cmd})

        # 렌더
        screen.fill(COLOR_BG)

        tiles = server_state.get("tiles", [])
        players = server_state.get("players", {})
        battles = server_state.get("battles", [])

        # 타일
        for t in tiles:
            q, r = t["q"], t["r"]
            owner = t["owner"]
            cx, cy = axial_to_pixel(q, r)
            poly = hex_polygon(cx, cy, HEX_SIZE - 1)
            fill = COLOR_ALLY if owner == my_side else COLOR_ENEMY
            pygame.draw.polygon(screen, fill, poly)
            pygame.draw.polygon(screen, COLOR_GRID, poly, 1)

        # 점령 링
        for t in tiles:
            if t.get("capture_remain") is not None:
                q, r = t["q"], t["r"]
                cx, cy = axial_to_pixel(q, r)
                pygame.draw.circle(screen, COLOR_CAPTURE, (cx, cy), HEX_SIZE - 4, 2)
                txt = font_small.render(f"{t['capture_remain']:.1f}s", True, COLOR_CAPTURE)
                screen.blit(txt, (cx - txt.get_width()//2, cy - HEX_SIZE * 1.3))

        # 유닛
        for t in tiles:
            q, r = t["q"], t["r"]
            cx, cy = axial_to_pixel(q, r)
            u = t.get("unit")
            if not u:
                continue
            if u["is_pinpoint"]:
                col = COLOR_PINPOINT_ALLY if u["owner"] == my_side else COLOR_PINPOINT_ENEMY
                pygame.draw.circle(screen, col, (cx, cy), HEX_SIZE // 2)
            else:
                pygame.draw.circle(screen, COLOR_TEXT, (cx, cy), HEX_SIZE // 3, 2)
            if u["name"] == "Soldier":
                hp_txt = font_small.render(f"{int(u['health'])}", True, COLOR_TEXT)
                screen.blit(hp_txt, (cx - hp_txt.get_width()//2, cy + HEX_SIZE * 0.4))

        # 전투 타일 표시
        for b in battles:
            tq = b["tile"]["q"]
            tr = b["tile"]["r"]
            cx, cy = axial_to_pixel(tq, tr)
            pygame.draw.circle(screen, COLOR_BATTLE_RING, (cx, cy), HEX_SIZE - 4, 3)
            txt = font_small.render("⚔", True, COLOR_BATTLE_RING)
            screen.blit(txt, (cx - txt.get_width()//2, cy - HEX_SIZE))

        # 선택된 병 테두리
        if selected_tile is not None:
            sq, sr = selected_tile
            cx, cy = axial_to_pixel(sq, sr)
            pygame.draw.polygon(screen, COLOR_HL, hex_polygon(cx, cy, HEX_SIZE - 3), 3)

        # 상단 정보
        my_money = players.get(my_side, {}).get("money", 0)
        txt = font.render(
            f"Side: {my_side.upper()}  Money: {my_money}   (1~3 유닛 선택, 우클릭 배치, 좌클릭 이동)",
            True, COLOR_TEXT)
        screen.blit(txt, (12, 12))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
