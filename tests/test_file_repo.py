"""Тесты формата тестового репозитория (файл описания графа)."""

import os
import tempfile
import unittest

from depgraph.errors import RepositoryError
from depgraph.file_repo import (
    FileSource,
    load_file_source,
    parse_repo_text,
)
from helpers import write_text


class ParseTests(unittest.TestCase):
    """Разбор текста описания."""

    def test_basic(self):
        """Пакеты с зависимостями и без."""
        table = parse_repo_text("A: B C\nB:\nC: B\n")
        self.assertEqual(table, {"A": ("B", "C"), "B": (), "C": ("B",)})

    def test_comments_and_blank_lines(self):
        """Комментарии и пустые строки игнорируются."""
        text = "# заголовок\n\nA: B  # хвост\n   \nB:\n"
        self.assertEqual(parse_repo_text(text), {"A": ("B",), "B": ()})

    def test_multi_letter_names(self):
        """Имя может состоять из нескольких букв."""
        table = parse_repo_text("AB: BC\nBC:\n")
        self.assertEqual(table["AB"], ("BC",))

    def test_duplicate_dependencies_merged(self):
        """Повтор зависимости в строке схлопывается."""
        table = parse_repo_text("A: B B C B\nB:\nC:\n")
        self.assertEqual(table["A"], ("B", "C"))

    def test_spaces_around_colon(self):
        """Пробелы вокруг двоеточия допустимы."""
        self.assertEqual(parse_repo_text("A : B\nB :\n")["A"], ("B",))

    def test_crlf(self):
        """Переводы строк CRLF."""
        self.assertEqual(parse_repo_text("A: B\r\nB:\r\n")["B"], ())


class ParseErrorTests(unittest.TestCase):
    """Некорректные описания."""

    def assert_error(self, text, fragment):
        """Проверить, что разбор падает с нужным сообщением."""
        with self.assertRaises(RepositoryError) as ctx:
            parse_repo_text(text)
        self.assertIn(fragment, str(ctx.exception))

    def test_lowercase_name(self):
        """Имя пакета строчными буквами."""
        self.assert_error("a: B\n", "ожидается")

    def test_lowercase_dependency(self):
        """Зависимость строчными буквами."""
        self.assert_error("A: b\n", "больших латинских")

    def test_digit_in_dependency(self):
        """Цифры в имени зависимости."""
        self.assert_error("A: B1\n", "больших латинских")

    def test_cyrillic_name(self):
        """Кириллица в имени."""
        self.assert_error("Б: А\n", "ожидается")

    def test_missing_colon(self):
        """Строка без двоеточия."""
        self.assert_error("A B C\n", "ожидается")

    def test_duplicate_package(self):
        """Пакет описан дважды."""
        self.assert_error("A: B\nA:\nB:\n", "описан повторно")

    def test_empty_text(self):
        """Пустое описание."""
        self.assert_error("", "нет ни одного пакета")

    def test_only_comments(self):
        """Только комментарии."""
        self.assert_error("# ничего\n\n", "нет ни одного пакета")

    def test_line_number_in_message(self):
        """В сообщении указан номер строки."""
        self.assert_error("A: B\nB:\nbad line\n", "строка 3")


class LoadTests(unittest.TestCase):
    """Загрузка из файла."""

    def setUp(self):
        """Создать временную директорию."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def test_load(self):
        """Корректный файл загружается."""
        path = write_text(self.dir, "A: B\nB:\n", name="repo.txt")
        source = load_file_source(path)
        self.assertTrue(source.has("A"))
        self.assertFalse(source.has("Z"))
        self.assertEqual(source.children("A"), ["B"])

    def test_missing_file(self):
        """Файл не существует."""
        with self.assertRaises(RepositoryError) as ctx:
            load_file_source(os.path.join(self.dir, "none.txt"))
        self.assertIn("не удалось прочитать", str(ctx.exception))

    def test_directory(self):
        """Вместо файла указана директория."""
        with self.assertRaises(RepositoryError):
            load_file_source(self.dir)

    def test_not_utf8(self):
        """Файл не в UTF-8."""
        path = write_text(self.dir, b"\xff\xfe\x00", name="r.txt", mode="wb")
        with self.assertRaises(RepositoryError) as ctx:
            load_file_source(path)
        self.assertIn("UTF-8", str(ctx.exception))

    def test_error_mentions_path(self):
        """Ошибка разбора содержит путь к файлу."""
        path = write_text(self.dir, "oops\n", name="bad.txt")
        with self.assertRaises(RepositoryError) as ctx:
            load_file_source(path)
        self.assertIn("bad.txt", str(ctx.exception))
        self.assertIn("строка 1", str(ctx.exception))


class SourceTests(unittest.TestCase):
    """Поведение FileSource."""

    def test_unresolved_dependencies(self):
        """Неописанные зависимости запоминаются."""
        source = FileSource(parse_repo_text("A: B Q\nB:\n"))
        self.assertEqual(source.children("A"), ["B", "Q"])
        self.assertEqual(source.unresolved, {"Q"})

    def test_unknown_package_has_no_children(self):
        """У неизвестного пакета нет зависимостей."""
        source = FileSource(parse_repo_text("A:\n"))
        self.assertEqual(source.children("Z"), [])


if __name__ == "__main__":
    unittest.main()
