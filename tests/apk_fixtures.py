"""Тестовые данные: индекс APKINDEX и локальный HTTP-сервер."""

import functools
import gzip
import io
import tarfile
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOCALHOST = "127.0.0.1"
ARCH_DIR = "x86_64"
INDEX_FILE = "APKINDEX.tar.gz"
POLL_SECONDS = 0.01

SAMPLE_INDEX = """C:Q1aaaa=
P:busybox
V:1.36.1-r29
A:x86_64
D:so:libc.musl-x86_64.so.1 musl>=1.2.5 !conflicting
p:cmd:busybox=1.36.1-r29 cmd:sh

C:Q1bbbb=
P:musl
V:1.2.5-r0
A:x86_64
p:so:libc.musl-x86_64.so.1=1

C:Q1cccc=
P:app
V:1.0-r0
D:busybox

C:Q1dddd=
P:app
V:2.0-r0
D:musl busybox>=1.36
"""


def add_members(archive, members):
    """Добавить в tar-архив пары (имя, байты)."""
    for name, content in members:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))


def tar_bytes(members):
    """Собрать законченный tar-архив."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        add_members(archive, members)
    return buffer.getvalue()


def partial_tar_bytes(members):
    """Собрать tar без завершающих блоков (как подпись в APKINDEX)."""
    buffer = io.BytesIO()
    archive = tarfile.TarFile(fileobj=buffer, mode="w")
    add_members(archive, members)
    return buffer.getvalue()


def build_archive(index_text, signed=True, member="APKINDEX"):
    """Собрать APKINDEX.tar.gz; с подписью - из двух gzip-потоков."""
    body = [("DESCRIPTION", b"test"), (member, index_text.encode())]
    result = gzip.compress(tar_bytes(body))
    if signed:
        sign = partial_tar_bytes([(".SIGN.RSA.test.rsa.pub", b"sig")])
        result = gzip.compress(sign) + result
    return result


class QuietHandler(SimpleHTTPRequestHandler):
    """HTTP-обработчик без вывода журнала в консоль."""

    def log_message(self, *_args):
        """Не писать журнал запросов."""


def start_server(testcase, files):
    """Запустить локальный сервер и вернуть его базовый URL.

    Args:
        testcase: тест, к которому привязана остановка сервера.
        files: словарь 'относительный путь -> байты'.
    """
    tmp = tempfile.TemporaryDirectory()
    for relative, content in files.items():
        path = Path(tmp.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    handler = functools.partial(QuietHandler, directory=tmp.name)
    server = ThreadingHTTPServer((LOCALHOST, 0), handler)
    thread = threading.Thread(
        target=server.serve_forever, args=(POLL_SECONDS,), daemon=True
    )
    thread.start()

    def stop():
        """Остановить сервер и удалить временные файлы."""
        server.shutdown()
        server.server_close()
        tmp.cleanup()

    testcase.addCleanup(stop)
    return f"http://{LOCALHOST}:{server.server_address[1]}"


def start_repo(testcase, index_text=SAMPLE_INDEX, signed=True):
    """Запустить сервер с репозиторием; вернуть URL каталога x86_64."""
    archive = build_archive(index_text, signed=signed)
    base = start_server(testcase, {f"{ARCH_DIR}/{INDEX_FILE}": archive})
    return f"{base}/{ARCH_DIR}"
