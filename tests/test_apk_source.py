"""Тесты источника данных на основе индекса Alpine."""

import unittest

from depgraph.apk_index import parse_index
from depgraph.apk_source import AlpineSource
from depgraph.graph import build_graph

INDEX = """P:app
V:1.0-r0
D:so:libfoo.so.1 libbar cmd:sh missing-lib

P:foo
V:2.0-r0
p:so:libfoo.so.1=1

P:libbar
V:1.0-r0

P:bar-provider
V:1.0-r0
p:libbar=1.0

P:busybox
V:1.0-r0
D:so:libc.so
p:cmd:sh

P:musl
V:1.0-r0
p:so:libc.so

P:selfish
V:1.0-r0
D:cmd:self
p:cmd:self

P:dup
V:1.0-r0
D:foo so:libfoo.so.1 foo>=1

P:multi
V:1.0-r0
D:old

P:multi
V:2.0-r0
D:new

P:old
V:1

P:new
V:1
"""


def make_source(name, version):
    """Создать источник с корнем name версии version."""
    packages = parse_index(INDEX)
    pinned = next(
        pkg for pkg in packages
        if pkg.name == name and pkg.version == version
    )
    return AlpineSource(packages, pinned)


class ResolveTests(unittest.TestCase):
    """Сопоставление зависимостей пакетам."""

    def test_names_and_virtual_names(self):
        """Прямые имена и виртуальные имена (so:, cmd:)."""
        source = make_source("app", "1.0-r0")
        self.assertEqual(
            source.children("app"),
            ["foo", "libbar", "busybox", "missing-lib"],
        )

    def test_package_name_beats_provider(self):
        """Пакет с точным именем важнее поставщика этого имени."""
        source = make_source("app", "1.0-r0")
        self.assertIn("libbar", source.children("app"))
        self.assertNotIn("bar-provider", source.children("app"))

    def test_unresolved_remembered(self):
        """Неразрешённая зависимость остаётся листом и запоминается."""
        source = make_source("app", "1.0-r0")
        source.children("app")
        self.assertEqual(source.unresolved, {"missing-lib"})
        self.assertEqual(source.children("missing-lib"), [])

    def test_self_provided_dependency_skipped(self):
        """Зависимость от собственного виртуального имени пропускается."""
        source = make_source("selfish", "1.0-r0")
        self.assertEqual(source.children("selfish"), [])

    def test_duplicates_merged(self):
        """Разные записи одной зависимости дают одну вершину."""
        source = make_source("dup", "1.0-r0")
        self.assertEqual(source.children("dup"), ["foo"])

    def test_pinned_version_is_used(self):
        """Для корня берётся выбранная версия, а не первая в индексе."""
        self.assertEqual(make_source("multi", "2.0-r0").children("multi"),
                         ["new"])
        self.assertEqual(make_source("multi", "1.0-r0").children("multi"),
                         ["old"])

    def test_has(self):
        """Проверка существования пакета."""
        source = make_source("app", "1.0-r0")
        self.assertTrue(source.has("musl"))
        self.assertFalse(source.has("so:libc.so"))
        self.assertFalse(source.has("nope"))


class TransitiveTests(unittest.TestCase):
    """Граф по индексу Alpine."""

    def test_transitive_through_virtual_names(self):
        """Транзитивные зависимости через виртуальные имена."""
        source = make_source("app", "1.0-r0")
        graph = build_graph(source, "app", "")
        self.assertEqual(graph.edges["busybox"], ("musl",))
        self.assertEqual(
            graph.transitive(),
            ["foo", "libbar", "busybox", "missing-lib", "musl"],
        )
        self.assertEqual(graph.unresolved, ("missing-lib",))

    def test_filter_on_real_names(self):
        """Фильтр действует на имена пакетов индекса."""
        source = make_source("app", "1.0-r0")
        graph = build_graph(source, "app", "bus")
        self.assertEqual(graph.excluded, ("busybox",))
        self.assertNotIn("musl", graph.edges)


if __name__ == "__main__":
    unittest.main()
