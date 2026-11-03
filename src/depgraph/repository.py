"""Получение индекса пакетов Alpine по HTTP(S) и его распаковка."""

import io
import tarfile
import urllib.error
import urllib.request
import zlib

from depgraph.apk_index import parse_index
from depgraph.errors import RepositoryError

INDEX_ARCHIVE = "APKINDEX.tar.gz"
INDEX_MEMBER = "APKINDEX"
TIMEOUT_SECONDS = 30
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
MAX_INDEX_BYTES = 500 * 1024 * 1024
USER_AGENT = "depgraph/0.1"


def index_url(repository):
    """Вернуть URL архива APKINDEX.tar.gz для адреса репозитория.

    Адрес может указывать на каталог архитектуры
    (.../v3.20/main/x86_64) или сразу на файл APKINDEX.tar.gz.
    """
    base = repository.rstrip("/")
    if base.endswith(INDEX_ARCHIVE):
        return base
    return f"{base}/{INDEX_ARCHIVE}"


def download(url):
    """Скачать файл по URL и вернуть его содержимое в байтах.

    Raises:
        RepositoryError: ошибка сети, HTTP-ошибка или слишком большой файл.
    """
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as reply:
            data = reply.read(MAX_DOWNLOAD_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RepositoryError(
            f"сервер вернул ошибку {exc.code} ({exc.reason}) для {url}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RepositoryError(
            f"не удалось подключиться к {url}: {exc.reason}"
        ) from exc
    except (OSError, ValueError) as exc:
        raise RepositoryError(f"не удалось загрузить {url}: {exc}") from exc
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise RepositoryError(f"файл {url} слишком большой")
    return data


def read_member(archive):
    """Прочитать файл APKINDEX из открытого tar-архива."""
    stream = archive.extractfile(archive.getmember(INDEX_MEMBER))
    if stream is None:
        raise RepositoryError(f"'{INDEX_MEMBER}' в архиве не файл")
    raw = stream.read(MAX_INDEX_BYTES + 1)
    if len(raw) > MAX_INDEX_BYTES:
        raise RepositoryError("индекс слишком большой после распаковки")
    return raw.decode("utf-8", errors="replace")


def extract_index(data):
    """Достать текст APKINDEX из байтов архива APKINDEX.tar.gz.

    Raises:
        RepositoryError: архив повреждён или в нём нет файла APKINDEX.
    """
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            return read_member(archive)
    except KeyError as exc:
        raise RepositoryError(
            f"в архиве нет файла '{INDEX_MEMBER}'"
        ) from exc
    except (tarfile.TarError, OSError, EOFError, zlib.error) as exc:
        raise RepositoryError(f"повреждённый архив индекса: {exc}") from exc


def load_packages(repository):
    """Скачать индекс репозитория и вернуть список пакетов.

    Raises:
        RepositoryError: не удалось получить или разобрать индекс.
    """
    url = index_url(repository)
    data = download(url)
    try:
        return parse_index(extract_index(data))
    except RepositoryError as exc:
        raise RepositoryError(f"{exc} (источник: {url})") from exc
