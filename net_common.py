# net_common.py
import json
import socket

ENCODING = "utf-8"

# 소켓별 수신 버퍼
_recv_buffers = {}
_decoder = json.JSONDecoder()


def send_json(sock: socket.socket, data: dict):
    """
    JSON 객체 하나를 전송.
    \n 으로 구분을 두지만, 파싱은 스트림 기반으로 진행한다.
    """
    msg = json.dumps(data, separators=(",", ":")).encode(ENCODING)
    msg += b"\n"
    sock.sendall(msg)


def recv_json(sock: socket.socket):
    """
    스트림에서 JSON 객체를 하나씩 꺼내는 함수.
    여러 JSON이 한 번에 오거나, 나눠서 와도 안전하게 처리한다.
    """
    buf = _recv_buffers.get(sock, b"")

    while True:
        if buf:
            text = buf.decode(ENCODING)
            text_stripped = text.lstrip()

            if not text_stripped:
                buf = b""
                _recv_buffers[sock] = buf
            else:
                try:
                    obj, idx = _decoder.raw_decode(text_stripped)
                    consumed_len = len(text) - len(text_stripped) + idx
                    remaining = text[consumed_len:]
                    _recv_buffers[sock] = remaining.encode(ENCODING)
                    return obj
                except json.JSONDecodeError:
                    # 데이터가 부족한 경우 – 더 받는다.
                    pass

        chunk = sock.recv(4096)
        if not chunk:
            _recv_buffers.pop(sock, None)
            return None

        buf += chunk
        _recv_buffers[sock] = buf
