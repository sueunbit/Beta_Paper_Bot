"""One local writer at a time, automatically released if the process exits."""
from contextlib import contextmanager
import os
import paper_bot as bot

@contextmanager
def single_writer():
    path = bot.ROOT / '.paper_bot.lock'
    stream = path.open('a+b')
    stream.seek(0, 2)
    if stream.tell() == 0:
        stream.write(b'0'); stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError('같은 폴더에서 다른 수집/요약 작업이 실행 중입니다. 먼저 종료하세요.') from None
    try:
        yield
    finally:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
