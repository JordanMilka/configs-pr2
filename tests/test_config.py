"""Тесты загрузки и проверки конфигурации."""

import os
import tempfile
import unittest

from depgraph.config import load_config
from depgraph.errors import ConfigError
from helpers import make_config, write_text, write_yaml


class ConfigTestCase(unittest.TestCase):
    """Базовый класс: временная директория и проверка ошибок."""

    def setUp(self):
        """Создать временную директорию."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def problems_for(self, data):
        """Записать конфигурацию и вернуть текст всех ошибок."""
        path = write_yaml(self.dir, data)
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        return " | ".join(ctx.exception.problems)


class ValidConfigTests(ConfigTestCase):
    """Корректные конфигурации."""

    def test_valid_url_mode(self):
        """Корректная конфигурация с URL загружается."""
        config = load_config(write_yaml(self.dir, make_config()))
        self.assertEqual(config.package_name, "busybox")
        self.assertFalse(config.test_mode)
        self.assertTrue(config.ascii_tree)
        self.assertEqual(config.filter_substring, "musl")

    def test_valid_test_mode(self):
        """В тестовом режиме принимается путь к существующему файлу."""
        repo = write_text(self.dir, "A: B\n", name="repo.txt")
        data = make_config(
            package_name="A", repository=repo, test_mode=True
        )
        config = load_config(write_yaml(self.dir, data))
        self.assertEqual(config.repository, repo)

    def test_empty_filter_allowed(self):
        """Пустая подстрока фильтрации допустима."""
        data = make_config(filter_substring="")
        config = load_config(write_yaml(self.dir, data))
        self.assertEqual(config.filter_substring, "")

    def test_as_pairs_order(self):
        """as_pairs возвращает все шесть параметров."""
        config = load_config(write_yaml(self.dir, make_config()))
        keys = [key for key, _ in config.as_pairs()]
        self.assertIn("package_version", keys)
        self.assertEqual(keys[0], "package_name")


class FileErrorTests(ConfigTestCase):
    """Ошибки чтения файла и структуры."""

    def test_missing_file(self):
        """Несуществующий файл конфигурации."""
        with self.assertRaises(ConfigError) as ctx:
            load_config(os.path.join(self.dir, "nope.yaml"))
        self.assertIn("не найден", ctx.exception.problems[0])

    def test_directory_instead_of_file(self):
        """Вместо файла указана директория."""
        with self.assertRaises(ConfigError) as ctx:
            load_config(self.dir)
        self.assertIn("не удалось прочитать", ctx.exception.problems[0])

    def test_invalid_yaml(self):
        """Синтаксически неверный YAML."""
        path = write_text(self.dir, "key: [unclosed\n")
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("некорректный YAML", ctx.exception.problems[0])

    def test_not_utf8(self):
        """Файл не в UTF-8."""
        path = write_text(self.dir, b"\xff\xfe\x00bad", mode="wb")
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("UTF-8", ctx.exception.problems[0])

    def test_empty_file(self):
        """Пустой файл."""
        path = write_text(self.dir, "")
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("словарём", ctx.exception.problems[0])

    def test_root_is_list(self):
        """Корень файла - список."""
        path = write_text(self.dir, "- a\n- b\n")
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_unknown_key(self):
        """Неизвестный параметр."""
        text = self.problems_for(make_config(depth=3))
        self.assertIn("неизвестный параметр 'depth'", text)

    def test_missing_key(self):
        """Отсутствует обязательный параметр."""
        data = make_config()
        del data["package_version"]
        text = self.problems_for(data)
        self.assertIn("отсутствует обязательный параметр", text)
        self.assertIn("package_version", text)


class ParamErrorTests(ConfigTestCase):
    """Ошибки значений отдельных параметров."""

    def test_package_name_errors(self):
        """Некорректное имя пакета."""
        for bad in ("", "-bad", "has space", "имя", 42, None):
            with self.subTest(value=bad):
                text = self.problems_for(make_config(package_name=bad))
                self.assertIn("package_name", text)

    def test_repository_not_url(self):
        """В обычном режиме repository должен быть http(s) URL."""
        for bad in ("ftp://host/x", "just/a/path", "http://", "", 5):
            with self.subTest(value=bad):
                text = self.problems_for(make_config(repository=bad))
                self.assertIn("repository", text)

    def test_repository_file_missing(self):
        """В тестовом режиме файл должен существовать."""
        missing = os.path.join(self.dir, "none.txt")
        data = make_config(repository=missing, test_mode=True)
        self.assertIn("файл не найден", self.problems_for(data))

    def test_repository_is_directory(self):
        """В тестовом режиме путь не может быть директорией."""
        data = make_config(repository=self.dir, test_mode=True)
        self.assertIn("не является файлом", self.problems_for(data))

    def test_url_in_test_mode(self):
        """В тестовом режиме URL вместо файла - ошибка."""
        data = make_config(test_mode=True)
        self.assertIn("файл не найден", self.problems_for(data))

    def test_test_mode_not_bool(self):
        """test_mode должен быть логическим."""
        for bad in ("yes", 1, None, "true"):
            with self.subTest(value=bad):
                text = self.problems_for(make_config(test_mode=bad))
                self.assertIn("test_mode", text)

    def test_version_errors(self):
        """Некорректная версия пакета."""
        for bad in ("", "abc", "1..2", "1.2.3-x", 1.5, None):
            with self.subTest(value=bad):
                text = self.problems_for(make_config(package_version=bad))
                self.assertIn("package_version", text)

    def test_valid_versions(self):
        """Допустимые версии Alpine принимаются."""
        for good in ("1", "1.2.3", "1.2.3-r0", "2.0_rc1", "1.0a"):
            with self.subTest(value=good):
                data = make_config(package_version=good)
                config = load_config(write_yaml(self.dir, data))
                self.assertEqual(config.package_version, good)

    def test_ascii_tree_not_bool(self):
        """ascii_tree должен быть логическим."""
        text = self.problems_for(make_config(ascii_tree="да"))
        self.assertIn("ascii_tree", text)

    def test_filter_errors(self):
        """Некорректная подстрока фильтрации."""
        for bad in ("a b", "\t", 7, None):
            with self.subTest(value=bad):
                text = self.problems_for(make_config(filter_substring=bad))
                self.assertIn("filter_substring", text)

    def test_all_problems_reported(self):
        """Все ошибки выводятся за один запуск."""
        data = make_config(
            package_name="", package_version="x", ascii_tree=3
        )
        text = self.problems_for(data)
        for name in ("package_name", "package_version", "ascii_tree"):
            self.assertIn(name, text)


if __name__ == "__main__":
    unittest.main()
