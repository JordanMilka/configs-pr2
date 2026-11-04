"""Этап 4: обратные зависимости - пакеты, зависящие от заданного."""

from depgraph.graph import build_graph
from depgraph.reverse import ReverseSource
from depgraph.stage3 import format_notes, open_source

SUMMARY = "этап 4: вывести обратные зависимости пакета (кто от него зависит)"
NO_DEPENDENTS = "(никто не зависит)"


def format_edges(graph):
    """Строки обхода BFS: 'пакет [уровень] <- зависящие от него'."""
    lines = []
    for name, dependents in graph.edges.items():
        targets = ", ".join(dependents) if dependents else NO_DEPENDENTS
        lines.append(f"  {name} [{graph.levels[name]}] <- {targets}")
    return lines


def format_cycles(graph):
    """Строки с циклами, найденными среди зависящих пакетов."""
    if not graph.cycles:
        return ["Циклические зависимости: нет"]
    lines = [f"Циклические зависимости ({len(graph.cycles)}):"]
    for cycle in graph.cycles:
        lines.append("  " + " <- ".join(cycle + cycle[:1]))
    return lines


def format_graph(graph, substring):
    """Сформировать полный вывод этапа 4."""
    dependents = graph.transitive()
    names = ", ".join(dependents) if dependents else "нет"
    lines = [
        f"Пакет: {graph.root}",
        "Обратные зависимости (порядок BFS, [уровень], "
        "'<-' ведёт к зависящим пакетам):",
    ]
    lines.extend(format_edges(graph))
    lines.append(f"Пакеты, зависящие от {graph.root} ({len(dependents)}): "
                 f"{names}")
    lines.extend(format_cycles(graph))
    lines.extend(format_notes(graph, substring))
    return lines


def run(config, stream):
    """Построить граф обратных зависимостей пакета и вывести его."""
    source = ReverseSource(open_source(config))
    graph = build_graph(source, config.package_name, config.filter_substring)
    print("\n".join(format_graph(graph, config.filter_substring)),
          file=stream)
