"""Тесты обратных зависимостей (этап 4)."""

import unittest

from apk_fixtures import SAMPLE_INDEX
from depgraph.apk_index import find_package, parse_index
from depgraph.apk_source import AlpineSource
from depgraph.errors import RepositoryError
from depgraph.file_repo import FileSource, parse_repo_text
from depgraph.graph import build_graph
from depgraph.reverse import ReverseSource

TEXT = """A: B C
B: D
C: D
D:
E: F
F: G
G: E H
H:
I: I J
J:
K: KB BK L
KB: L
BK: L
L:
M: N Z
Z:
P: Q
Q: R
R: S
S:
"""


def reverse(root, substring=""):
    """Построить граф обратных зависимостей для репозитория TEXT."""
    source = ReverseSource(FileSource(parse_repo_text(TEXT)))
    return build_graph(source, root, substring)


class ReverseSourceTests(unittest.TestCase):
    """Поведение ReverseSource."""

    def setUp(self):
        """Создать источник по тестовому репозиторию."""
        self.source = ReverseSource(FileSource(parse_repo_text(TEXT)))

    def test_children_are_direct_dependents(self):
        """Дети пакета - пакеты, напрямую зависящие от него."""
        self.assertEqual(self.source.children("D"), ["B", "C"])
        self.assertEqual(self.source.children("L"), ["K", "KB", "BK"])

    def test_order_follows_repository(self):
        """Порядок зависящих пакетов совпадает с порядком файла."""
        self.assertEqual(self.source.children("S"), ["R"])

    def test_no_dependents(self):
        """У пакета, от которого никто не зависит, нет детей."""
        self.assertEqual(self.source.children("A"), [])

    def test_has_described_and_mentioned(self):
        """Известны и описанные, и только упомянутые пакеты."""
        self.assertTrue(self.source.has("A"))
        self.assertTrue(self.source.has("N"))
        self.assertFalse(self.source.has("Q9"))

    def test_self_dependency_is_kept(self):
        """Зависимость пакета от самого себя сохраняется."""
        self.assertEqual(self.source.children("I"), ["I"])

    def test_names_of_file_source(self):
        """FileSource.names возвращает описанные пакеты по порядку."""
        names = FileSource(parse_repo_text("B: A\nA:\n")).names()
        self.assertEqual(names, ["B", "A"])


class ReverseGraphTests(unittest.TestCase):
    """Обратные зависимости тем же обходом BFS."""

    def test_diamond_is_transitive(self):
        """Зависящие пакеты ищутся транзитивно, без повторов."""
        graph = reverse("D")
        self.assertEqual(graph.transitive(), ["B", "C", "A"])
        self.assertEqual(graph.levels, {"D": 0, "B": 1, "C": 1, "A": 2})

    def test_chain_levels(self):
        """Уровни цепочки растут с каждым шагом."""
        graph = reverse("S")
        self.assertEqual(graph.transitive(), ["R", "Q", "P"])
        self.assertEqual(graph.levels["P"], 3)

    def test_no_dependents(self):
        """От пакета никто не зависит."""
        graph = reverse("A")
        self.assertFalse(graph.transitive())
        self.assertEqual(graph.edges, {"A": ()})

    def test_cycle(self):
        """Цикл находится, обход завершается."""
        graph = reverse("E")
        self.assertEqual(graph.transitive(), ["G", "F"])
        self.assertEqual(graph.cycles, (("E", "G", "F"),))

    def test_self_dependency(self):
        """Зависимость от себя - цикл из одного пакета."""
        graph = reverse("J")
        self.assertEqual(graph.transitive(), ["I"])
        self.assertEqual(graph.cycles, (("I",),))

    def test_filter_prunes_dependents(self):
        """Фильтр исключает пакеты и тех, кто зависит только через них."""
        graph = reverse("L", "B")
        self.assertEqual(graph.transitive(), ["K"])
        self.assertEqual(graph.excluded, ("BK", "KB"))

    def test_filter_cuts_branch(self):
        """Исключённый пакет закрывает путь к зависящим от него."""
        graph = reverse("S", "R")
        self.assertFalse(graph.transitive())
        self.assertEqual(graph.excluded, ("R",))

    def test_mentioned_only_root(self):
        """Корень, не описанный в файле, но упомянутый как зависимость."""
        graph = reverse("N")
        self.assertEqual(graph.transitive(), ["M"])

    def test_unknown_root(self):
        """Неизвестный пакет."""
        with self.assertRaises(RepositoryError) as ctx:
            reverse("Q9")
        self.assertIn("'Q9' не найден", str(ctx.exception))

    def test_root_excluded_by_filter(self):
        """Корень с подстрокой фильтра - ошибка."""
        with self.assertRaises(RepositoryError):
            reverse("KB", "B")

    def test_reverse_is_inverse_of_forward(self):
        """Если B достижим от A вперёд, то A достижим от B назад."""
        source = FileSource(parse_repo_text(TEXT))
        forward = build_graph(source, "A", "")
        for name in forward.transitive():
            back = reverse(name)
            self.assertIn("A", back.transitive())


class AlpineReverseTests(unittest.TestCase):
    """Обратные зависимости по индексу Alpine."""

    def setUp(self):
        """Разобрать тестовый индекс."""
        self.packages = parse_index(SAMPLE_INDEX)

    def source(self, name, version):
        """Создать обратный источник с корнем name версии version."""
        pinned = find_package(self.packages, name, version)
        return ReverseSource(AlpineSource(self.packages, pinned))

    def test_names(self):
        """names возвращает имена без повторов (app - один раз)."""
        names = AlpineSource(self.packages, self.packages[0]).names()
        self.assertEqual(names, ["busybox", "musl", "app"])

    def test_dependents_through_provides(self):
        """Зависимость через so: учитывается как зависимость от musl."""
        source = self.source("musl", "1.2.5-r0")
        graph = build_graph(source, "musl", "")
        self.assertEqual(graph.transitive(), ["busybox", "app"])
        self.assertEqual(graph.levels["app"], 2)

    def test_filter_on_alpine_names(self):
        """Фильтр действует на имена пакетов Alpine."""
        source = self.source("musl", "1.2.5-r0")
        graph = build_graph(source, "musl", "busy")
        self.assertFalse(graph.transitive())
        self.assertEqual(graph.excluded, ("busybox",))


if __name__ == "__main__":
    unittest.main()
