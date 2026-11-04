"""Сравнение depgraph со штатными инструментами apk (dot и info -R).

Эталоны tests/data/apk_tools получены настоящим apk-tools 2.14.4 в
Alpine 3.20.10. Граф depgraph строится по выгрузке индекса
tests/data/alpine_v3.20_main_subset.txt.
"""

import tempfile
import unittest
from pathlib import Path

from apk_dot import (
    name_pairs,
    node_names,
    parse_dot,
    reachable_pairs,
    split_node,
    versions,
)
from apk_fixtures import start_repo
from depgraph.apk_index import find_package, parse_index
from depgraph.apk_source import AlpineSource
from depgraph.cli import EXIT_OK
from depgraph.graph import build_graph
from helpers import make_config, run_cli, write_yaml

DATA = Path(__file__).resolve().parent / "data"
APK = DATA / "apk_tools"
ALTERNATIVES = frozenset(("dash", "dash-binsh", "yash", "yash-binsh"))
SHELL_LABEL = "/bin/sh"
DEPENDENCIES_HEADER = "Прямые зависимости"
EXTRA_NODES = {
    "alsaconf": ALTERNATIVES,
    "curl": ALTERNATIVES | {"libncursesw", "ncurses-terminfo-base"},
    "util-linux-dev": frozenset(),
}


def read(path):
    """Прочитать текстовый файл."""
    return path.read_text(encoding="utf-8")


def dot_edges(package):
    """Рёбра эталонного вывода apk dot для пакета."""
    return parse_dot(read(APK / f"dot_{package}.txt"))


def our_graph(package):
    """Граф depgraph для той же версии пакета, что выбрал apk."""
    version = versions(dot_edges(package))[package]
    packages = parse_index(read(DATA / "alpine_v3.20_main_subset.txt"))
    pinned = find_package(packages, package, version)
    return build_graph(AlpineSource(packages, pinned), package, "")


def our_pairs(graph):
    """Пары (пакет, зависимость) графа depgraph."""
    return {(name, child) for name, kids in graph.edges.items()
            for child in kids}


class DotParserTests(unittest.TestCase):
    """Разбор вывода apk dot."""

    def test_split_node(self):
        """Имя и версия делятся по последнему '-версия-rN'."""
        self.assertEqual(split_node("alsa-utils-1.2.11-r1"),
                         ("alsa-utils", "1.2.11-r1"))
        self.assertEqual(split_node("libncursesw-6.4_p20240420-r2"),
                         ("libncursesw", "6.4_p20240420-r2"))

    def test_labels_and_colors(self):
        """Метка зависимости и красный цвет читаются из атрибутов."""
        edges = dot_edges("alsaconf")
        labeled = [e for e in edges if e.label == "so:libc.musl-x86_64.so.1"]
        self.assertTrue(labeled)
        self.assertTrue(any(edge.red for edge in edges))
        direct = [e for e in edges if not e.label]
        self.assertIn("alsaconf-1.2.11-r1", {e.source for e in direct})


class GraphComparisonTests(unittest.TestCase):
    """Граф depgraph и граф apk dot."""

    def test_same_package_versions(self):
        """Версии пакетов в apk dot совпадают с нашей выгрузкой индекса."""
        packages = parse_index(read(DATA / "alpine_v3.20_main_subset.txt"))
        ours = {pkg.name: pkg.version for pkg in packages}
        for package in EXTRA_NODES:
            with self.subTest(package=package):
                for name, version in versions(dot_edges(package)).items():
                    if name in ours:
                        self.assertEqual(ours[name], version, name)

    def test_identical_when_no_alternatives(self):
        """util-linux-dev: рёбра и узлы совпадают полностью."""
        edges = dot_edges("util-linux-dev")
        graph = our_graph("util-linux-dev")
        self.assertEqual(our_pairs(graph), name_pairs(edges))
        self.assertEqual(set(graph.edges), node_names(edges))

    def test_ours_is_subset_of_apk_dot(self):
        """Все рёбра depgraph есть и в apk dot."""
        for package in EXTRA_NODES:
            with self.subTest(package=package):
                graph = our_graph(package)
                pairs = name_pairs(dot_edges(package))
                self.assertLessEqual(our_pairs(graph), pairs)

    def test_extra_nodes_of_apk_dot(self):
        """Лишние узлы apk dot - альтернативные поставщики /bin/sh."""
        for package, extra in EXTRA_NODES.items():
            with self.subTest(package=package):
                nodes = node_names(dot_edges(package))
                self.assertEqual(nodes - set(our_graph(package).edges),
                                 set(extra))

    def test_extra_edges_touch_extra_nodes_only(self):
        """Лишние рёбра apk dot ведут только в лишние узлы или из них."""
        for package, extra in EXTRA_NODES.items():
            with self.subTest(package=package):
                pairs = name_pairs(dot_edges(package))
                only_apk = pairs - our_pairs(our_graph(package))
                for source, target in only_apk:
                    self.assertTrue({source, target} & set(extra))

    def test_equal_after_removing_alternatives(self):
        """Без альтернатив и недостижимых пакетов графы совпадают."""
        for package in EXTRA_NODES:
            with self.subTest(package=package):
                pairs = name_pairs(dot_edges(package))
                rest = reachable_pairs(pairs, package, ALTERNATIVES)
                self.assertEqual(rest, our_pairs(our_graph(package)))

    def test_alternatives_come_from_shell_dependency(self):
        """Рёбра в альтернативные пакеты от остальных - зависимость /bin/sh."""
        for package in ("alsaconf", "curl"):
            with self.subTest(package=package):
                for edge in dot_edges(package):
                    source = split_node(edge.source)[0]
                    target = split_node(edge.target)[0]
                    if target in ALTERNATIVES and source not in ALTERNATIVES:
                        self.assertEqual(edge.label, SHELL_LABEL)

    def test_red_edges_connect_alternatives(self):
        """Красные рёбра apk dot соединяют только альтернативы."""
        for package in EXTRA_NODES:
            with self.subTest(package=package):
                for edge in dot_edges(package):
                    if edge.red:
                        pair = {split_node(edge.source)[0],
                                split_node(edge.target)[0]}
                        self.assertLessEqual(pair, ALTERNATIVES)

    def test_apk_dot_repeats_edges(self):
        """apk dot рисует одну пару дважды (по имени и по so:-имени)."""
        edges = dot_edges("alsaconf")
        self.assertGreater(len(edges), len(name_pairs(edges)))

    def test_shell_providers_and_our_choice(self):
        """apk dot показывает трёх поставщиков /bin/sh, мы берём первого."""
        for package in ("alsaconf", "curl"):
            with self.subTest(package=package):
                providers = {
                    split_node(edge.target)[0]
                    for edge in dot_edges(package)
                    if edge.label == SHELL_LABEL
                }
                self.assertEqual(
                    providers, {"busybox-binsh", "dash-binsh", "yash-binsh"})
                graph = our_graph(package)
                self.assertIn("busybox-binsh", graph.edges)
                self.assertNotIn("dash-binsh", graph.edges)
                self.assertNotIn("yash-binsh", graph.edges)


class DirectDependenciesTests(unittest.TestCase):
    """stage2 и apk info -R."""

    def setUp(self):
        """Запустить локальный репозиторий с выгрузкой индекса."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.repo = start_repo(
            self, read(DATA / "alpine_v3.20_main_subset.txt"))

    def test_stage2_equals_apk_info(self):
        """Прямые зависимости stage2 совпадают с apk info -R."""
        for package in EXTRA_NODES:
            with self.subTest(package=package):
                version = versions(dot_edges(package))[package]
                data = make_config(
                    package_name=package, package_version=version,
                    repository=self.repo,
                )
                path = write_yaml(self.dir, data)
                code, out, _ = run_cli(["stage2", "-c", path])
                self.assertEqual(code, EXIT_OK)
                ours = [line.strip() for line in out.splitlines()
                        if line.startswith("  ")]
                info = read(APK / f"info_R_{package}.txt").splitlines()
                theirs = [line.strip() for line in info[1:]
                          if line.strip()]
                self.assertEqual(ours, theirs)
                self.assertIn(DEPENDENCIES_HEADER, out)


if __name__ == "__main__":
    unittest.main()
