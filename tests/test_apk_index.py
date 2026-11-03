"""Тесты разбора индекса APKINDEX."""

import unittest

from apk_fixtures import SAMPLE_INDEX
from depgraph.apk_index import (
    find_package,
    parse_dependency,
    parse_depends,
    parse_index,
)
from depgraph.errors import RepositoryError


class ParseDependencyTests(unittest.TestCase):
    """Разбор отдельных записей зависимостей."""

    def test_plain_name(self):
        """Имя без ограничения версии."""
        dep = parse_dependency("musl")
        self.assertEqual((dep.name, dep.operator, dep.version),
                         ("musl", "", ""))

    def test_version_constraints(self):
        """Операторы сравнения версий."""
        cases = {
            "musl>=1.2.5": ("musl", ">=", "1.2.5"),
            "zlib<2": ("zlib", "<", "2"),
            "pc:zlib=1.3": ("pc:zlib", "=", "1.3"),
            "foo~1.2": ("foo", "~", "1.2"),
            "bar=~1.2": ("bar", "=~", "1.2"),
        }
        for token, expected in cases.items():
            with self.subTest(token=token):
                dep = parse_dependency(token)
                self.assertEqual(
                    (dep.name, dep.operator, dep.version), expected
                )
                self.assertEqual(dep.raw, token)

    def test_virtual_names(self):
        """Виртуальные имена so: и cmd: сохраняются целиком."""
        dep = parse_dependency("so:libc.musl-x86_64.so.1")
        self.assertEqual(dep.name, "so:libc.musl-x86_64.so.1")
        self.assertEqual(dep.operator, "")

    def test_malformed_token(self):
        """Некорректная запись не вызывает исключения."""
        dep = parse_dependency(">=1")
        self.assertEqual(dep.raw, ">=1")

    def test_conflicts_skipped(self):
        """Конфликты (!имя) не считаются зависимостями."""
        deps = parse_depends("a !b c>=1")
        self.assertEqual([dep.raw for dep in deps], ["a", "c>=1"])

    def test_empty_depends(self):
        """Пустое поле D даёт пустой кортеж."""
        self.assertFalse(parse_depends(""))


class ParseIndexTests(unittest.TestCase):
    """Разбор индекса целиком."""

    def test_packages_and_versions(self):
        """Имена и версии всех записей."""
        packages = parse_index(SAMPLE_INDEX)
        pairs = [(pkg.name, pkg.version) for pkg in packages]
        self.assertEqual(pairs, [
            ("busybox", "1.36.1-r29"),
            ("musl", "1.2.5-r0"),
            ("app", "1.0-r0"),
            ("app", "2.0-r0"),
        ])

    def test_dependencies_of_busybox(self):
        """Зависимости busybox в порядке следования, без конфликтов."""
        busybox = parse_index(SAMPLE_INDEX)[0]
        self.assertEqual(
            [dep.raw for dep in busybox.depends],
            ["so:libc.musl-x86_64.so.1", "musl>=1.2.5"],
        )
        self.assertIn("cmd:sh", busybox.provides)

    def test_no_depends_field(self):
        """Запись без поля D не имеет зависимостей."""
        musl = parse_index(SAMPLE_INDEX)[1]
        self.assertFalse(musl.depends)

    def test_crlf_and_extra_blank_lines(self):
        """Переводы строк CRLF и лишние пустые строки."""
        text = "P:a\r\nV:1\r\nD:b\r\n\r\n\r\nP:b\r\nV:2\r\n"
        packages = parse_index(text)
        self.assertEqual([pkg.name for pkg in packages], ["a", "b"])
        self.assertEqual(packages[0].depends[0].name, "b")

    def test_incomplete_records_skipped(self):
        """Записи без P или V пропускаются."""
        packages = parse_index("P:a\n\nV:1\n\nP:b\nV:2\n")
        self.assertEqual([pkg.name for pkg in packages], ["b"])

    def test_empty_text(self):
        """Пустой индекс - пустой список."""
        self.assertFalse(parse_index(""))


class FindPackageTests(unittest.TestCase):
    """Поиск пакета и версии."""

    def setUp(self):
        """Разобрать тестовый индекс."""
        self.packages = parse_index(SAMPLE_INDEX)

    def test_exact_version(self):
        """Выбирается запись с указанной версией."""
        package = find_package(self.packages, "app", "1.0-r0")
        self.assertEqual(package.version, "1.0-r0")
        package = find_package(self.packages, "app", "2.0-r0")
        self.assertEqual(package.depends[0].name, "musl")

    def test_unknown_package(self):
        """Неизвестный пакет."""
        with self.assertRaises(RepositoryError) as ctx:
            find_package(self.packages, "nope", "1")
        self.assertIn("'nope' не найден", str(ctx.exception))

    def test_unknown_version_lists_available(self):
        """При неверной версии выводятся доступные."""
        with self.assertRaises(RepositoryError) as ctx:
            find_package(self.packages, "app", "9.9")
        message = str(ctx.exception)
        self.assertIn("'9.9'", message)
        self.assertIn("1.0-r0, 2.0-r0", message)

    def test_version_must_match_exactly(self):
        """Префикс версии не считается совпадением."""
        with self.assertRaises(RepositoryError):
            find_package(self.packages, "busybox", "1.36.1")


if __name__ == "__main__":
    unittest.main()
