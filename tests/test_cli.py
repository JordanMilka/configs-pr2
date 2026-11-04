"""Тесты интерфейса командной строки."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from apk_fixtures import start_repo
from depgraph.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_DATA_ERROR,
    EXIT_OK,
    main,
)
from helpers import make_config, run_cli, write_text, write_yaml

ROOT = Path(__file__).resolve().parent.parent


class Stage1Tests(unittest.TestCase):
    """Команда stage1: вывод параметров конфигурации."""

    def setUp(self):
        """Создать временную директорию."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def test_prints_all_params(self):
        """Все параметры выводятся в формате ключ-значение."""
        path = write_yaml(self.dir, make_config())
        code, out, _ = run_cli(["stage1", "--config", path])
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
        _, out, _ = run_cli(["stage1", "-c", path])
        self.assertIn('filter_substring: ""', out)

    def test_needs_no_network(self):
        """stage1 не обращается к репозиторию (адрес недоступен)."""
        data = make_config(repository="http://127.0.0.1:1/x86_64")
        path = write_yaml(self.dir, data)
        code, out, _ = run_cli(["stage1", "-c", path])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("127.0.0.1", out)

    def test_config_error(self):
        """Ошибка конфигурации - код 2, stdout пуст."""
        path = write_yaml(self.dir, make_config(package_name=""))
        code, out, err = run_cli(["stage1", "-c", path])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertFalse(out)
        self.assertIn("Ошибка конфигурации", err)


class CommandLineTests(unittest.TestCase):
    """Разбор аргументов командной строки."""

    def parse_failure(self, argv):
        """Вернуть (код, stderr) для аргументов, вызывающих выход."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main(argv)
        return ctx.exception.code, err.getvalue()

    def test_command_required(self):
        """Без команды этапа программа завершается с кодом 2."""
        code, err = self.parse_failure([])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("КОМАНДА", err)

    def test_unknown_command(self):
        """Неизвестная команда."""
        code, err = self.parse_failure(["stage9"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("stage9", err)

    def test_config_before_command_rejected(self):
        """Опция --config указывается после команды этапа."""
        code, _ = self.parse_failure(["--config", "x.yaml", "stage1"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)

    def test_help_lists_stages(self):
        """Справка перечисляет команды этапов."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                main(["--help"])
        self.assertEqual(ctx.exception.code, EXIT_OK)
        self.assertIn("stage1", out.getvalue())
        self.assertIn("stage2", out.getvalue())

    def test_unknown_option(self):
        """Неизвестная опция."""
        code, _ = self.parse_failure(["stage1", "--bogus"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)


class Stage3TestModeTests(unittest.TestCase):
    """Команда stage3 с тестовым репозиторием (файл описания графа)."""

    def setUp(self):
        """Создать временную директорию."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def run_repo(self, text, **overrides):
        """Записать репозиторий и запустить stage3 в тестовом режиме."""
        repo = write_text(self.dir, text, name="repo.txt")
        overrides.setdefault("package_name", "A")
        data = make_config(repository=repo, test_mode=True, **overrides)
        path = write_yaml(self.dir, data)
        return run_cli(["stage3", "-c", path])

    def test_diamond(self):
        """Граф с общей зависимостью."""
        code, out, _ = self.run_repo("A: B C\nB: D\nC: D\nD:\n",
                                     filter_substring="")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("  A [0] -> B, C", out)
        self.assertIn("  D [2] -> (нет зависимостей)", out)
        self.assertIn("Транзитивные зависимости (3): B, C, D", out)
        self.assertIn("Циклические зависимости: нет", out)

    def test_cycle(self):
        """Цикл выводится, программа завершается."""
        code, out, _ = self.run_repo("A: B\nB: C\nC: A\n",
                                     filter_substring="")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Циклические зависимости (1):", out)
        self.assertIn("  A -> B -> C -> A", out)

    def test_self_loop(self):
        """Зависимость от самого себя."""
        _, out, _ = self.run_repo("A: A\n", filter_substring="")
        self.assertIn("  A -> A", out)
        self.assertIn("Транзитивные зависимости (0): нет", out)

    def test_filter(self):
        """Фильтр исключает пакеты и выводит их список."""
        text = "A: AB BA C\nAB: C\nBA:\nC:\n"
        code, out, _ = self.run_repo(text, filter_substring="B")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Исключено фильтром 'B': AB, BA", out)
        self.assertIn("Транзитивные зависимости (1): C", out)

    def test_filter_without_matches(self):
        """Фильтр, которому ничего не соответствует."""
        _, out, _ = self.run_repo("A: B\nB:\n", filter_substring="Q")
        self.assertIn("Исключено фильтром 'Q': нет", out)

    def test_unresolved(self):
        """Неописанная зависимость перечисляется."""
        _, out, _ = self.run_repo("A: B X\nB:\n", filter_substring="")
        self.assertIn("Не найдены в репозитории (1): X", out)

    def test_version_is_ignored(self):
        """В тестовом режиме версия пакета не используется."""
        code, _, _ = self.run_repo("A:\n", filter_substring="",
                                   package_version="9.9.9")
        self.assertEqual(code, EXIT_OK)

    def test_unknown_root(self):
        """Корневого пакета нет в файле - код 3."""
        code, out, err = self.run_repo("A: B\nB:\n", package_name="Q",
                                       filter_substring="")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertFalse(out)
        self.assertIn("'Q' не найден", err)

    def test_root_excluded_by_filter(self):
        """Корень содержит подстроку фильтра - код 3."""
        code, _, err = self.run_repo("A:\n", filter_substring="A")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("исключён", err)

    def test_syntax_error_in_repo_file(self):
        """Ошибка формата файла репозитория - код 3 с номером строки."""
        code, _, err = self.run_repo("A: B\nневерно\n",
                                     filter_substring="")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("строка 2", err)

    def test_missing_repo_file(self):
        """Несуществующий файл - ошибка конфигурации (код 2)."""
        missing = os.path.join(self.dir, "none.txt")
        data = make_config(repository=missing, test_mode=True)
        path = write_yaml(self.dir, data)
        code, _, err = run_cli(["stage3", "-c", path])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("файл не найден", err)


class Stage3ExamplesTests(unittest.TestCase):
    """Демонстрационные конфигурации из каталога examples."""

    def run_example(self, name):
        """Запустить stage3 с примером из корня репозитория."""
        cwd = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, cwd)
        return run_cli(["stage3", "-c", f"examples/{name}"])

    def test_examples(self):
        """Каждый пример даёт ожидаемый фрагмент вывода."""
        cases = {
            "config_test_mode.yaml": "Транзитивные зависимости (3): B, C, D",
            "config_test_cycle.yaml": "E -> F -> G -> E",
            "config_test_self_loop.yaml": "  I -> I",
            "config_test_filter.yaml": "Исключено фильтром 'B': BK, KB",
            "config_test_unresolved.yaml": "Не найдены в репозитории (1): N",
            "config_test_leaf.yaml": "Y [0] -> (нет зависимостей)",
        }
        for name, expected in cases.items():
            with self.subTest(example=name):
                code, out, _ = self.run_example(name)
                self.assertEqual(code, EXIT_OK)
                self.assertIn(expected, out)


class Stage3RealRepoTests(unittest.TestCase):
    """Команда stage3 с реальным (локально эмулируемым) репозиторием."""

    def setUp(self):
        """Создать временную директорию и локальный репозиторий."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.repo = start_repo(self)

    def run_with(self, **overrides):
        """Запустить stage3 с конфигурацией для локального репозитория."""
        overrides.setdefault("repository", self.repo)
        path = write_yaml(self.dir, make_config(**overrides))
        return run_cli(["stage3", "-c", path])

    def test_transitive_through_provides(self):
        """Транзитивные зависимости с учётом виртуальных имён."""
        code, out, _ = self.run_with(
            package_name="app", package_version="2.0-r0",
            filter_substring="",
        )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("  app [0] -> musl, busybox", out)
        self.assertIn("  busybox [1] -> musl", out)
        self.assertIn("Транзитивные зависимости (2): musl, busybox", out)

    def test_filter(self):
        """Фильтр по подстроке имени пакета Alpine."""
        _, out, _ = self.run_with(
            package_name="app", package_version="2.0-r0",
            filter_substring="busy",
        )
        self.assertIn("Исключено фильтром 'busy': busybox", out)
        self.assertIn("Транзитивные зависимости (1): musl", out)

    def test_unknown_version(self):
        """Неизвестная версия корня - код 3."""
        code, _, err = self.run_with(package_version="0.0",
                                     filter_substring="")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("доступные версии", err)


class CliTests(unittest.TestCase):
    """Команда stage2 на локальном репозитории."""

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
        path = write_yaml(self.dir, data)
        return run_cli(["stage2", "--config", path])

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

    def test_test_mode_not_supported(self):
        """Этап 2 работает только с URL, тестовый режим - в stage3."""
        repo_file = write_text(self.dir, "A: B\n", name="repo.txt")
        code, _, err = self.run_with(
            package_name="A", repository=repo_file, test_mode=True
        )
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("stage3", err)

    def test_config_error_exit_code(self):
        """Ошибка конфигурации - код 2, stdout пуст."""
        path = write_yaml(self.dir, make_config(package_name=""))
        code, out, err = run_cli(["stage2", "-c", path])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertFalse(out)
        self.assertIn("Ошибка конфигурации", err)

    def test_missing_config_file(self):
        """Несуществующий файл конфигурации."""
        missing = os.path.join(self.dir, "x.yaml")
        code, _, err = run_cli(["stage2", "-c", missing])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("не найден", err)

    def test_default_config_missing(self):
        """Без аргументов и без config.yaml - ошибка, а не падение."""
        cwd = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, cwd)
        code, _, err = run_cli(["stage2"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("config.yaml", err)


if __name__ == "__main__":
    unittest.main()
