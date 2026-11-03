"""Тесты интерфейса командной строки."""

import contextlib
import io
import os
import tempfile
import unittest

from apk_fixtures import start_repo
from depgraph.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_DATA_ERROR,
    EXIT_OK,
    main,
)
from helpers import make_config, write_text, write_yaml


def run_cli(args):
    """Запустить main и вернуть (код, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    """Проверка поведения CLI на локальном репозитории."""

    def setUp(self):
        """Создать временную директорию и локальный репозиторий."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.repo = start_repo(self)

    def run_with(self, **overrides):
        """Запустить CLI с конфигурацией, указывающей на репозиторий."""
        overrides.setdefault("repository", self.repo)
        data = make_config(**overrides)
        return run_cli(["--config", write_yaml(self.dir, data)])

    def test_prints_direct_dependencies(self):
        """Выводятся все прямые зависимости пакета."""
        code, out, _ = self.run_with()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Пакет: busybox 1.36.1-r29", out)
        self.assertIn("Прямые зависимости (2):", out)
        self.assertIn("  so:libc.musl-x86_64.so.1", out)
        self.assertIn("  musl>=1.2.5", out)
        self.assertNotIn("conflicting", out)

    def test_dependencies_of_selected_version(self):
        """Берутся зависимости именно указанной версии."""
        _, out, _ = self.run_with(package_name="app",
                                  package_version="1.0-r0")
        self.assertIn("  busybox\n", out + "\n")
        self.assertNotIn("musl", out)
        _, out, _ = self.run_with(package_name="app",
                                  package_version="2.0-r0")
        self.assertIn("  busybox>=1.36", out)

    def test_package_without_dependencies(self):
        """У пакета без зависимостей выводится 'нет'."""
        _, out, _ = self.run_with(package_name="musl",
                                  package_version="1.2.5-r0")
        self.assertIn("Прямые зависимости: нет", out)

    def test_unknown_package(self):
        """Неизвестный пакет - код 3 и сообщение в stderr."""
        code, out, err = self.run_with(package_name="nope")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertFalse(out)
        self.assertIn("'nope' не найден", err)

    def test_unknown_version(self):
        """Неизвестная версия - сообщение с доступными версиями."""
        code, _, err = self.run_with(package_version="0.0")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("1.36.1-r29", err)

    def test_repository_unreachable(self):
        """Недоступный каталог репозитория - код 3."""
        code, _, err = self.run_with(repository=self.repo + "/missing")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("404", err)

    def test_test_mode_not_supported_yet(self):
        """Тестовый режим пока не поддержан."""
        repo_file = write_text(self.dir, "A: B\n", name="repo.txt")
        code, _, err = self.run_with(
            package_name="A", repository=repo_file, test_mode=True
        )
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("этапе 3", err)

    def test_config_error_exit_code(self):
        """Ошибка конфигурации - код 2, stdout пуст."""
        path = write_yaml(self.dir, make_config(package_name=""))
        code, out, err = run_cli(["-c", path])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertFalse(out)
        self.assertIn("Ошибка конфигурации", err)

    def test_missing_config_file(self):
        """Несуществующий файл конфигурации."""
        code, _, err = run_cli(["-c", os.path.join(self.dir, "x.yaml")])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("не найден", err)

    def test_default_config_missing(self):
        """Без аргументов и без config.yaml - ошибка, а не падение."""
        cwd = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, cwd)
        code, _, err = run_cli([])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("config.yaml", err)

    def test_unknown_argument(self):
        """Неизвестный аргумент обрабатывает argparse."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main(["--bogus"])
        self.assertEqual(ctx.exception.code, EXIT_CONFIG_ERROR)


if __name__ == "__main__":
    unittest.main()
