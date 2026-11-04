"""Тесты на реальных записях индекса Alpine v3.20 (main, x86_64).

Данные tests/data/alpine_v3.20_main_subset.txt - выгрузка реального
индекса для графов alsaconf, curl и util-linux-dev. Эталонный вывод
tests/data/real_stage3_outputs.txt получен на полном реальном индексе.
"""

import tempfile
import unittest
from pathlib import Path

from apk_fixtures import start_repo
from depgraph.apk_index import find_package
from depgraph.apk_source import AlpineSource
from depgraph.cli import EXIT_DATA_ERROR, EXIT_OK
from depgraph.graph import build_graph
from depgraph.repository import load_packages
from helpers import make_config, run_cli, write_yaml

DATA = Path(__file__).resolve().parent / "data"
HEADER = "### "
TRANSITIVE_COUNT = 15
CASES = (
    ("alsaconf", "1.2.11-r1", 3),
    ("curl", "8.14.1-r2", 4),
    ("util-linux-dev", "2.40.1-r1", 5),
)


def read_data(name):
    """Прочитать файл из tests/data."""
    return (DATA / name).read_text(encoding="utf-8")


def read_reference():
    """Разобрать эталонный вывод: словарь 'имя версия' -> текст."""
    blocks, key = {}, None
    for line in read_data("real_stage3_outputs.txt").split("\n"):
        if line.startswith(HEADER):
            key = line[len(HEADER):]
            blocks[key] = []
        elif key:
            blocks[key].append(line)
    return {name: "\n".join(lines).strip("\n")
            for name, lines in blocks.items()}


class RealPackagesTests(unittest.TestCase):
    """Граф реальных пакетов глубиной 3, 4 и 5 уровней."""

    def setUp(self):
        """Запустить локальный репозиторий с реальными записями."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.repo = start_repo(self, read_data(
            "alpine_v3.20_main_subset.txt"))

    def graph(self, name, version, substring=""):
        """Построить граф пакета по реальным данным."""
        packages = load_packages(self.repo)
        pinned = find_package(packages, name, version)
        source = AlpineSource(packages, pinned)
        return build_graph(source, name, substring)

    def run_stage3(self, name, version, substring=""):
        """Запустить команду stage3 и вернуть (код, stdout, stderr)."""
        data = make_config(
            package_name=name, package_version=version,
            repository=self.repo, filter_substring=substring,
        )
        return run_cli(["stage3", "-c", write_yaml(self.dir, data)])

    def test_depth_and_size(self):
        """Глубина 3, 4, 5; по 15 зависимостей; без циклов."""
        for name, version, depth in CASES:
            with self.subTest(package=name):
                graph = self.graph(name, version)
                self.assertEqual(max(graph.levels.values()), depth)
                self.assertEqual(len(graph.transitive()),
                                 TRANSITIVE_COUNT)
                self.assertFalse(graph.cycles)
                self.assertFalse(graph.unresolved)

    def test_output_matches_real_index(self):
        """Вывод stage3 совпадает с выводом на полном реальном индексе."""
        reference = read_reference()
        for name, version, _depth in CASES:
            with self.subTest(package=name):
                code, out, _ = self.run_stage3(name, version)
                self.assertEqual(code, EXIT_OK)
                self.assertEqual(out.strip("\n"),
                                 reference[f"{name} {version}"])

    def test_virtual_names_resolved(self):
        """Виртуальные имена (so:, /bin/sh) превращены в пакеты."""
        edges = self.graph("alsaconf", "1.2.11-r1").edges
        self.assertEqual(edges["bash"],
                         ("busybox-binsh", "musl", "readline"))
        self.assertIn("alsa-lib", edges["alsa-utils"])
        self.assertEqual(edges["busybox-binsh"], ("busybox",))

    def test_versioned_dependency_resolved_by_name(self):
        """Зависимость alsa-utils=1.2.11-r1 найдена по имени пакета."""
        graph = self.graph("alsaconf", "1.2.11-r1")
        self.assertEqual(graph.edges["alsaconf"], ("alsa-utils", "bash"))

    def test_shared_dependencies_appear_once(self):
        """Общие зависимости (musl) входят в граф один раз."""
        graph = self.graph("curl", "8.14.1-r2")
        self.assertEqual(list(graph.edges).count("musl"), 1)
        self.assertEqual(graph.levels["musl"], 1)

    def test_filter_prunes_subtree(self):
        """Фильтр 'ssl' исключает libssl3, остальное остаётся."""
        graph = self.graph("curl", "8.14.1-r2", "ssl")
        self.assertEqual(graph.excluded, ("libssl3",))
        self.assertNotIn("libssl3", graph.edges)
        self.assertIn("libcrypto3", graph.edges)

    def test_filter_removes_whole_branch(self):
        """Фильтр 'libcurl' убирает ветку целиком."""
        graph = self.graph("curl", "8.14.1-r2", "libcurl")
        self.assertEqual(graph.transitive(), ["musl", "zlib"])

    def test_wrong_version_lists_available(self):
        """Неверная версия: код 3 и список доступных версий."""
        code, _, err = self.run_stage3("curl", "1.0")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("8.14.1-r2", err)

    def test_stage2_direct_dependencies(self):
        """Команда stage2 выводит прямые зависимости как в индексе."""
        data = make_config(
            package_name="curl", package_version="8.14.1-r2",
            repository=self.repo,
        )
        code, out, _ = run_cli(["stage2", "-c", write_yaml(self.dir, data)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Прямые зависимости (4):", out)
        self.assertIn("  libcurl=8.14.1-r2", out)
        self.assertIn("  so:libz.so.1", out)


if __name__ == "__main__":
    unittest.main()
