# net_common.py
import json
import socket

ENCODING = "utf-8"

# 소켓별로 남은 수신 버퍼를 저장
_recv_buffers = {}
_decoder = json.JSONDecoder()


def send_json(sock: socket.socket, data: dict):
    """
    JSON 객체 하나를 전송.
    끝에 개행을 붙이지만, 프로토콜상으로는 단순 구분자일 뿐이고
    recv_json은 개행이 없어도 동작하게 설계한다.
    """
    msg = json.dumps(data, separators=(",", ":")).encode(ENCODING)
    # 가독성을 위해 개행 하나 덧붙임 (없어도 동작하지만, 디버깅 편의를 위해 유지)
    msg += b"\n"
    sock.sendall(msg)


def recv_json(sock: socket.socket):
    """
    스트림에서 JSON 객체를 '하나씩' 꺼내는 함수.
    - TCP에서 여러 JSON이 한 번에 오더라도 첫 번째만 파싱하고,
      나머지는 버퍼에 남겨둔다.
    - JSON이 반쯤만 와도 남겨뒀다가 다음 recv에서 이어서 파싱한다.
    """
    buf = _recv_buffers.get(sock, b"")

    while True:
        if buf:
            # 문자열로 변환
            text = buf.decode(ENCODING)
            # 앞쪽 공백 제거 (개행, 스페이스 등)
            text_stripped = text.lstrip()

            # 아무것도 없으면 더 받기
            if not text_stripped:
                buf = b""
                _recv_buffers[sock] = buf
            else:
                try:
                    # raw_decode는 문자열 맨 앞에서 JSON 하나만 파싱하고,
                    # 어디까지 읽었는지 인덱스를 함께 돌려준다.
                    obj, idx = _decoder.raw_decode(text_stripped)

                    # 파싱한 부분 이후에 남은 데이터들 (다음 JSON) 버퍼에 다시 저장
                    # text_stripped 앞에서 몇 글자 잘랐는지 보정
                    consumed_len = len(text) - len(text_stripped) + idx
                    remaining = text[consumed_len:]
                    _recv_buffers[sock] = remaining.encode(ENCODING)

                    return obj

                except json.JSONDecodeError:
                    # 데이터가 더 필요해서 실패한 경우일 수 있으니, 추가 수신을 시도
                    pass

        # 여기까지 왔다는 건:
        # - buf가 비어 있거나
        # - 아직 JSON 하나를 완전히 파싱하기에 데이터가 부족하다는 뜻
        chunk = sock.recv(4096)
        if not chunk:
            # 연결 끊김
            _recv_buffers.pop(sock, None)
            return None

        buf += chunk
        _recv_buffers[sock] = buf
