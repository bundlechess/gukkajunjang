# net_common.py
import json
import socket

ENCODING = "utf-8"

def send_json(sock: socket.socket, data: dict):
    """
    \n 으로 끝나는 한 줄 JSON 패킷 전송.
    """
    msg = json.dumps(data).encode(ENCODING) + b"\n"
    sock.sendall(msg)


def recv_json(sock: socket.socket):
    """
    \n 기준으로 한 줄 JSON 읽기.
    블로킹 호출이라서, 별도 스레드에서 쓰는 걸 추천.
    """
    buf = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            # 연결 끊김
            return None
        buf += chunk
        if b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if not line.strip():
                continue
            return json.loads(line.decode(ENCODING))
