"""Тесты построения графа зависимостей (BFS с рекурсией)."""

import unittest

from depgraph.errors import RepositoryError
from depgraph.file_repo import FileSource, parse_repo_text
from depgraph.graph import build_graph, find_cycles


def make_source(text):
    """Создать тестовый источник из текста описания репозитория."""
    return FileSource(parse_repo_text(text))


def build(text, root="A", substring=""):
    """Построить граф для репозитория, заданного текстом."""
    return build_graph(make_source(text), root, substring)


class ChainSource:
    """Цепочка пакетов P0 -> P1 -> ... заданной длины."""

    def __init__(self, length):
        """Запомнить длину цепочки."""
        self.length = length
        self.unresolved = set()

    def has(self, name):
        """Любой пакет цепочки существует."""
        return bool(name)

    def children(self, name):
        """Вернуть следующий пакет цепочки."""
        index = int(name[1:])
        return [f"P{index + 1}"] if index < self.length else []


class BfsTests(unittest.TestCase):
    """Порядок обхода, уровни и транзитивность."""

    def test_diamond(self):
        """Общая зависимость присутствует в графе один раз."""
        graph = build("A: B C\nB: D\nC: D\nD:\n")
        self.assertEqual(list(graph.edges), ["A", "B", "C", "D"])
        self.assertEqual(graph.edges["A"], ("B", "C"))
        self.assertEqual(graph.edges["D"], ())
        self.assertEqual(graph.transitive(), ["B", "C", "D"])

    def test_levels_are_shortest_distance(self):
        """Уровень вершины - кратчайшее расстояние от корня (BFS)."""
        graph = build("A: B F\nB: F\nF:\n")
        self.assertEqual(graph.levels, {"A": 0, "B": 1, "F": 1})

    def test_transitive_chain(self):
        """Транзитивные зависимости через несколько уровней."""
        graph = build("A: B\nB: C\nC: D\nD:\n")
        self.assertEqual(graph.transitive(), ["B", "C", "D"])
        self.assertEqual(graph.levels["D"], graph.levels["C"] + 1)

    def test_unreachable_packages_not_included(self):
        """Недостижимые из корня пакеты в граф не попадают."""
        graph = build("A: B\nB:\nX: Y\nY:\n")
        self.assertNotIn("X", graph.edges)
        self.assertNotIn("Y", graph.edges)

    def test_leaf_root(self):
        """Корень без зависимостей."""
        graph = build("A:\n")
        self.assertEqual(graph.edges, {"A": ()})
        self.assertFalse(graph.transitive())
        self.assertFalse(graph.cycles)


class CycleTests(unittest.TestCase):
    """Циклические зависимости."""

    def test_simple_cycle(self):
        """Цикл через корень находится и обход завершается."""
        graph = build("A: B\nB: C\nC: A D\nD:\n")
        self.assertEqual(graph.cycles, (("A", "B", "C"),))
        self.assertEqual(graph.transitive(), ["B", "C", "D"])

    def test_two_node_cycle_excludes_root_from_transitive(self):
        """Корень не входит в свои транзитивные зависимости."""
        graph = build("A: B\nB: A\n")
        self.assertEqual(graph.transitive(), ["B"])
        self.assertEqual(graph.cycles, (("A", "B"),))

    def test_self_dependency(self):
        """Зависимость пакета от самого себя."""
        graph = build("A: A B\nB:\n")
        self.assertEqual(graph.cycles, (("A",),))
        self.assertEqual(graph.transitive(), ["B"])

    def test_cycle_not_through_root(self):
        """Цикл, до которого корень лишь доходит."""
        graph = build("A: B\nB: C\nC: B\n")
        self.assertEqual(graph.cycles, (("B", "C"),))

    def test_same_cycle_reported_once(self):
        """Один цикл, найденный с разных сторон, считается один раз."""
        graph = build("A: B C\nB: C\nC: B\n")
        self.assertEqual(graph.cycles, (("B", "C"),))

    def test_two_different_cycles(self):
        """Два разных цикла."""
        graph = build("A: B C\nB: A\nC: A\n")
        self.assertEqual(set(graph.cycles), {("A", "B"), ("A", "C")})

    def test_no_cycles_in_dag(self):
        """В ациклическом графе циклов нет."""
        graph = build("A: B C\nB: D\nC: D\nD:\n")
        self.assertEqual(graph.cycles, ())

    def test_find_cycles_function(self):
        """find_cycles напрямую по словарю рёбер."""
        edges = {"A": ("B",), "B": ("C",), "C": ("A",)}
        self.assertEqual(find_cycles("A", edges), [("A", "B", "C")])


class FilterTests(unittest.TestCase):
    """Фильтрация по подстроке имени."""

    TEXT = "K: KB BK L\nKB: L M\nBK: L\nL:\nM:\n"

    def test_excluded_with_subtree(self):
        """Исключённые пакеты и их зависимости не учитываются."""
        graph = build(self.TEXT, root="K", substring="B")
        self.assertEqual(graph.transitive(), ["L"])
        self.assertEqual(graph.excluded, ("BK", "KB"))
        self.assertNotIn("M", graph.edges)

    def test_dependency_reachable_other_way_stays(self):
        """Пакет остаётся, если до него есть путь мимо исключённых."""
        graph = build("A: X B\nX: B\nB:\n", substring="X")
        self.assertEqual(graph.transitive(), ["B"])
        self.assertEqual(graph.excluded, ("X",))

    def test_empty_substring_disables_filter(self):
        """Пустая подстрока ничего не исключает."""
        graph = build(self.TEXT, root="K", substring="")
        self.assertEqual(len(graph.edges), len(parse_repo_text(self.TEXT)))
        self.assertEqual(graph.excluded, ())

    def test_filter_without_matches(self):
        """Подстрока, которой нет в именах."""
        graph = build("A: B\nB:\n", substring="Z")
        self.assertEqual(graph.excluded, ())
        self.assertEqual(graph.transitive(), ["B"])

    def test_substring_is_case_sensitive(self):
        """Регистр учитывается."""
        graph = build("A: B\nB:\n", substring="b")
        self.assertEqual(graph.transitive(), ["B"])

    def test_root_excluded_is_error(self):
        """Корневой пакет с подстрокой фильтра - ошибка."""
        with self.assertRaises(RepositoryError) as ctx:
            build(self.TEXT, root="KB", substring="B")
        self.assertIn("исключён", str(ctx.exception))

    def test_cycle_through_excluded_is_broken(self):
        """Цикл через исключённый пакет разрывается."""
        graph = build("A: B\nB: C\nC: A\n", substring="C")
        self.assertEqual(graph.cycles, ())


class ErrorTests(unittest.TestCase):
    """Ошибки и особые случаи."""

    def test_missing_root(self):
        """Корневого пакета нет в репозитории."""
        with self.assertRaises(RepositoryError) as ctx:
            build("A: B\nB:\n", root="Q")
        self.assertIn("'Q' не найден", str(ctx.exception))

    def test_unresolved_reported(self):
        """Неописанные зависимости попадают в unresolved."""
        graph = build("A: B Q\nB:\n")
        self.assertEqual(graph.unresolved, ("Q",))
        self.assertEqual(graph.edges["Q"], ())

    def test_long_chain_works(self):
        """Цепочка в сотню уровней обходится рекурсивно."""
        graph = build_graph(ChainSource(200), "P0", "")
        self.assertEqual(len(graph.transitive()), 200)

    def test_too_deep_graph(self):
        """Слишком глубокий граф даёт понятную ошибку."""
        with self.assertRaises(RepositoryError) as ctx:
            build_graph(ChainSource(5000), "P0", "")
        self.assertIn("слишком глубокий", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
