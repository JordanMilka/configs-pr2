"""Тесты интерфейса командной строки."""

import contextlib
import io
import os
import tempfile
import unittest

from depgraph.cli import EXIT_CONFIG_ERROR, EXIT_OK, main
from helpers import make_config, write_yaml


def run_cli(args):
    """Запустить main и вернуть (код, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    """Проверка поведения CLI."""

    def setUp(self):
        """Создать временную директорию."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def test_prints_all_params(self):
        """Все параметры выводятся в формате ключ-значение."""
        path = write_yaml(self.dir, make_config())
        code, out, _ = run_cli(["--config", path])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("package_name: busybox", out)
        self.assertIn("test_mode: false", out)
        self.assertIn("package_version: 1.36.1-r29", out)
        self.assertIn("ascii_tree: true", out)
        self.assertIn("filter_substring: musl", out)
        self.assertIn("repository: https://", out)

    def test_empty_filter_shown(self):
        """Пустая подстрока выводится как \"\"."""
        path = write_yaml(self.dir, make_config(filter_substring=""))
        _, out, _ = run_cli(["-c", path])
        self.assertIn('filter_substring: ""', out)

    def test_error_exit_code(self):
        """При ошибке код завершения ненулевой, stdout пуст."""
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
