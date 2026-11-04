"""Этап 5: визуализация графа зависимостей (Mermaid и ASCII-дерево)."""

from depgraph.graph import build_graph
from depgraph.stage3 import open_source
from depgraph.visualize import format_mermaid, format_tree

SUMMARY = "этап 5: вывести граф на языке Mermaid (и ASCII-дерево)"
TREE_TITLE = "ASCII-дерево зависимостей:"


def format_output(graph, ascii_tree):
    """Сформировать вывод: диаграмма Mermaid и, если нужно, дерево."""
    lines = format_mermaid(graph)
    if ascii_tree:
        lines.extend(["", TREE_TITLE])
        lines.extend(format_tree(graph))
    return lines


def run(config, stream):
    """Построить граф зависимостей пакета и вывести его визуализацию."""
    source = open_source(config)
    graph = build_graph(source, config.package_name, config.filter_substring)
    print("\n".join(format_output(graph, config.ascii_tree)), file=stream)
