"""Тесты получения и распаковки индекса репозитория."""

import gzip
import socket
import unittest
from unittest import mock

from apk_fixtures import (
    LOCALHOST,
    SAMPLE_INDEX,
    build_archive,
    start_repo,
    start_server,
    tar_bytes,
)
from depgraph import repository
from depgraph.errors import RepositoryError


class IndexUrlTests(unittest.TestCase):
    """Формирование URL индекса."""

    def test_directory_url(self):
        """К каталогу добавляется APKINDEX.tar.gz."""
        self.assertEqual(
            repository.index_url("http://h/alpine/main/x86_64"),
            "http://h/alpine/main/x86_64/APKINDEX.tar.gz",
        )

    def test_trailing_slash(self):
        """Завершающий слэш не удваивается."""
        self.assertEqual(
            repository.index_url("http://h/x86_64/"),
            "http://h/x86_64/APKINDEX.tar.gz",
        )

    def test_direct_file_url(self):
        """URL файла остаётся без изменений."""
        url = "http://h/x86_64/APKINDEX.tar.gz"
        self.assertEqual(repository.index_url(url), url)


class ExtractIndexTests(unittest.TestCase):
    """Распаковка архива индекса."""

    def test_signed_archive(self):
        """Архив с подписью в отдельном gzip-потоке."""
        data = build_archive(SAMPLE_INDEX, signed=True)
        self.assertEqual(repository.extract_index(data), SAMPLE_INDEX)

    def test_unsigned_archive(self):
        """Архив без подписи."""
        data = build_archive(SAMPLE_INDEX, signed=False)
        self.assertEqual(repository.extract_index(data), SAMPLE_INDEX)

    def test_missing_member(self):
        """В архиве нет файла APKINDEX."""
        data = build_archive(SAMPLE_INDEX, member="OTHER")
        with self.assertRaises(RepositoryError) as ctx:
            repository.extract_index(data)
        self.assertIn("нет файла 'APKINDEX'", str(ctx.exception))

    def test_not_gzip(self):
        """Данные не являются gzip."""
        with self.assertRaises(RepositoryError) as ctx:
            repository.extract_index(b"<html>not an archive</html>")
        self.assertIn("повреждённый архив", str(ctx.exception))

    def test_gzip_without_tar(self):
        """gzip с произвольными данными вместо tar."""
        with self.assertRaises(RepositoryError):
            repository.extract_index(gzip.compress(b"plain text only"))

    def test_truncated_archive(self):
        """Обрезанный архив."""
        data = build_archive(SAMPLE_INDEX, signed=False)
        with self.assertRaises(RepositoryError):
            repository.extract_index(data[: len(data) // 2])

    def test_member_is_not_file(self):
        """Пустой архив без нужного файла."""
        data = gzip.compress(tar_bytes([]))
        with self.assertRaises(RepositoryError):
            repository.extract_index(data)


class DownloadTests(unittest.TestCase):
    """Загрузка по HTTP с локального сервера."""

    def test_download_ok(self):
        """Успешная загрузка возвращает байты файла."""
        base = start_server(self, {"file.bin": b"payload"})
        self.assertEqual(repository.download(f"{base}/file.bin"), b"payload")

    def test_http_404(self):
        """Ответ 404 превращается в RepositoryError."""
        base = start_server(self, {"file.bin": b"x"})
        with self.assertRaises(RepositoryError) as ctx:
            repository.download(f"{base}/missing.bin")
        self.assertIn("404", str(ctx.exception))

    def test_connection_refused(self):
        """Сервер недоступен: порт никто не слушает."""
        with socket.socket() as sock:
            sock.bind((LOCALHOST, 0))
            port = sock.getsockname()[1]
        with self.assertRaises(RepositoryError) as ctx:
            repository.download(f"http://{LOCALHOST}:{port}/x")
        self.assertIn("не удалось", str(ctx.exception))

    def test_too_large(self):
        """Файл больше лимита отвергается."""
        base = start_server(self, {"big.bin": b"0123456789"})
        with mock.patch.object(repository, "MAX_DOWNLOAD_BYTES", 4):
            with self.assertRaises(RepositoryError) as ctx:
                repository.download(f"{base}/big.bin")
        self.assertIn("слишком большой", str(ctx.exception))

    def test_bad_url(self):
        """Некорректный URL."""
        with self.assertRaises(RepositoryError):
            repository.download("not a url")


class LoadPackagesTests(unittest.TestCase):
    """Полная цепочка: скачать, распаковать, разобрать."""

    def test_load_packages(self):
        """Загрузка пакетов с локального репозитория."""
        url = start_repo(self)
        packages = repository.load_packages(url)
        names = [pkg.name for pkg in packages]
        self.assertEqual(names, ["busybox", "musl", "app", "app"])

    def test_error_mentions_repository(self):
        """В сообщении об ошибке указан адрес индекса."""
        url = start_repo(self)
        with self.assertRaises(RepositoryError) as ctx:
            repository.load_packages(url + "/nonexistent")
        self.assertIn("APKINDEX.tar.gz", str(ctx.exception))

    def test_broken_index_on_server(self):
        """Сервер отдал повреждённый архив."""
        base = start_server(self, {"x86_64/APKINDEX.tar.gz": b"garbage"})
        with self.assertRaises(RepositoryError):
            repository.load_packages(f"{base}/x86_64")


if __name__ == "__main__":
    unittest.main()
