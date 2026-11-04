"""Тесты визуализации: Mermaid и ASCII-дерево."""

import unittest

from depgraph.file_repo import FileSource, parse_repo_text
from depgraph.graph import DependencyGraph, build_graph
from depgraph.visualize import (
    assign_ids,
    format_mermaid,
    format_tree,
    is_safe_id,
)

ROOT_STYLE = "    classDef root fill:#d0e6ff,stroke:#2b5c99,stroke-width:2px"
CHAIN_LENGTH = 5000


def graph_of(text, root):
    """Построить граф по тестовому репозиторию, заданному текстом."""
    return build_graph(FileSource(parse_repo_text(text)), root, "")


def manual_graph(root, edges, unresolved=()):
    """Создать граф вручную (для имён, которых нет в тестовом формате)."""
    return DependencyGraph(root, edges, {}, (), tuple(unresolved), ())


class MermaidTests(unittest.TestCase):
    """Описание графа на языке Mermaid."""

    def test_diamond(self):
        """Ромб: заголовок, рёбра в порядке BFS, стиль корня."""
        lines = format_mermaid(graph_of("A: B C\nB: D\nC: D\nD:\n", "A"))
        self.assertEqual(lines, [
            "graph TD",
            "    A --> B",
            "    A --> C",
            "    B --> D",
            "    C --> D",
            ROOT_STYLE,
            "    class A root",
        ])

    def test_root_without_dependencies(self):
        """Пакет без зависимостей объявляется отдельной строкой."""
        lines = format_mermaid(graph_of("Y:\n", "Y"))
        self.assertEqual(lines[:2], ["graph TD", '    Y["Y"]'])
        self.assertIn("    class Y root", lines)

    def test_cycle_edges(self):
        """Цикл рисуется обычными рёбрами."""
        lines = format_mermaid(graph_of("E: F\nF: G\nG: E H\nH:\n", "E"))
        self.assertIn("    G --> E", lines)
        self.assertIn("    G --> H", lines)

    def test_self_loop(self):
        """Зависимость от самого себя - ребро в ту же вершину."""
        lines = format_mermaid(graph_of("I: I J\nJ:\n", "I"))
        self.assertIn("    I --> I", lines)

    def test_missing_package_class(self):
        """Пакет, которого нет в репозитории, получает свой класс."""
        lines = format_mermaid(graph_of("M: N Z\nZ:\n", "M"))
        self.assertIn("    classDef missing stroke-dasharray:5 5", lines)
        self.assertIn("    class N missing", lines)

    def test_no_missing_class_when_all_found(self):
        """Без ненайденных пакетов класс missing не объявляется."""
        lines = format_mermaid(graph_of("A: B\nB:\n", "A"))
        self.assertFalse([line for line in lines if "missing" in line])

    def test_names_with_hyphens_get_labels(self):
        """Имена с дефисами получают безопасные идентификаторы."""
        edges = {"alsa-utils": ("musl", "libc.so"), "musl": (),
                 "libc.so": ()}
        lines = format_mermaid(manual_graph("alsa-utils", edges))
        self.assertIn('    n0["alsa-utils"]', lines)
        self.assertIn('    n1["libc.so"]', lines)
        self.assertIn("    n0 --> musl", lines)
        self.assertIn("    n0 --> n1", lines)
        self.assertIn("    class n0 root", lines)

    def test_reserved_word_is_not_an_id(self):
        """Служебное слово end не используется как идентификатор."""
        edges = {"root": ("end",), "end": ()}
        lines = format_mermaid(manual_graph("root", edges))
        self.assertIn('    n0["end"]', lines)
        self.assertIn("    root --> n0", lines)

    def test_generated_ids_do_not_clash(self):
        """Сгенерированный идентификатор не совпадает с именем пакета."""
        ids = assign_ids(["a-b", "n0"])
        self.assertEqual(ids["n0"], "n0")
        self.assertEqual(ids["a-b"], "n1")
        self.assertEqual(len(set(ids.values())), len(ids))

    def test_label_quotes_escaped(self):
        """Кавычки в имени экранируются."""
        lines = format_mermaid(manual_graph('a"b', {'a"b': ()}))
        self.assertIn('    n0["a#quot;b"]', lines)

    def test_is_safe_id(self):
        """Проверка допустимых идентификаторов."""
        for good in ("A", "busybox", "lib_x2"):
            self.assertTrue(is_safe_id(good), good)
        for bad in ("a-b", "1abc", "so:libc", "End", "graph", "a.b"):
            self.assertFalse(is_safe_id(bad), bad)

    def test_every_edge_is_drawn_once(self):
        """Число рёбер диаграммы равно числу рёбер графа."""
        graph = graph_of("A: B C\nB: D\nC: D\nD:\n", "A")
        edges = [line for line in format_mermaid(graph) if "-->" in line]
        expected = sum(len(kids) for kids in graph.edges.values())
        self.assertEqual(len(edges), expected)
        self.assertEqual(len(set(edges)), len(edges))


class TreeTests(unittest.TestCase):
    """ASCII-дерево зависимостей."""

    def test_diamond(self):
        """Ромб: общий лист показан под каждым родителем."""
        lines = format_tree(graph_of("A: B C\nB: D\nC: D\nD:\n", "A"))
        self.assertEqual(lines, [
            "A",
            "|-- B",
            "|   `-- D",
            "`-- C",
            "    `-- D",
        ])

    def test_shared_dependency_marked_once_expanded(self):
        """Повтор пакета с зависимостями помечается (*)."""
        text = "T: U V\nU: W\nV: W\nW: X\nX:\n"
        lines = format_tree(graph_of(text, "T"))
        self.assertEqual(lines, [
            "T",
            "|-- U",
            "|   `-- W",
            "|       `-- X",
            "`-- V",
            "    `-- W (*)",
            "(*) - зависимости этого пакета показаны выше",
        ])

    def test_cycle_marked(self):
        """Возврат к предку помечается (цикл), обход завершается."""
        lines = format_tree(graph_of("E: F\nF: G\nG: E H\nH:\n", "E"))
        self.assertIn("        |-- E (цикл)", lines)
        self.assertIn("        `-- H", lines)
        self.assertIn("(цикл) - пакет уже есть среди его предков", lines)

    def test_self_loop(self):
        """Самозависимость - (цикл) у корня."""
        lines = format_tree(graph_of("I: I J\nJ:\n", "I"))
        self.assertEqual(lines[:3], ["I", "|-- I (цикл)", "`-- J"])

    def test_single_package(self):
        """Дерево из одного пакета."""
        self.assertEqual(format_tree(graph_of("Y:\n", "Y")), ["Y"])

    def test_no_legend_without_marks(self):
        """Пояснения выводятся только для использованных пометок."""
        lines = format_tree(graph_of("A: B\nB:\n", "A"))
        self.assertEqual(lines, ["A", "`-- B"])

    def test_only_ascii_drawing(self):
        """Ветви дерева нарисованы только символами ASCII."""
        lines = format_tree(graph_of("A: B C\nB: D\nC:\nD:\n", "A"))
        drawing = "".join(line.split(" ")[0] for line in lines)
        self.assertTrue(drawing.isascii())

    def test_every_package_present(self):
        """Каждый пакет графа встречается в дереве."""
        graph = graph_of("A: B C\nB: D\nC: D E\nD:\nE:\n", "A")
        text = "\n".join(format_tree(graph))
        for name in graph.edges:
            self.assertIn(name, text)

    def test_deep_chain_without_recursion(self):
        """Очень глубокая цепочка выводится без рекурсии."""
        names = [f"P{index}" for index in range(CHAIN_LENGTH)]
        edges = {name: (nxt,) for name, nxt in zip(names, names[1:])}
        edges[names[-1]] = ()
        lines = format_tree(manual_graph(names[0], edges))
        self.assertEqual(len(lines), CHAIN_LENGTH)
        self.assertTrue(lines[-1].endswith(names[-1]))


if __name__ == "__main__":
    unittest.main()
