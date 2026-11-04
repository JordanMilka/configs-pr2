"""Этап 3: граф транзитивных зависимостей и основные операции."""

from depgraph.apk_index import find_package
from depgraph.apk_source import AlpineSource
from depgraph.file_repo import load_file_source
from depgraph.graph import build_graph
from depgraph.repository import load_packages

SUMMARY = "этап 3: построить граф транзитивных зависимостей (BFS)"
NO_DEPENDENCIES = "(нет зависимостей)"


def open_source(config):
    """Создать источник данных: тестовый файл или реальный репозиторий.

    Raises:
        RepositoryError: репозиторий недоступен, нет пакета или версии.
    """
    if config.test_mode:
        return load_file_source(config.repository)
    packages = load_packages(config.repository)
    pinned = find_package(
        packages, config.package_name, config.package_version
    )
    return AlpineSource(packages, pinned)


def format_edges(graph):
    """Строки графа в порядке обхода BFS: 'имя [уровень] -> зависимости'."""
    lines = []
    for name, children in graph.edges.items():
        targets = ", ".join(children) if children else NO_DEPENDENCIES
        lines.append(f"  {name} [{graph.levels[name]}] -> {targets}")
    return lines


def format_cycles(graph):
    """Строки с найденными циклами зависимостей."""
    if not graph.cycles:
        return ["Циклические зависимости: нет"]
    lines = [f"Циклические зависимости ({len(graph.cycles)}):"]
    for cycle in graph.cycles:
        lines.append("  " + " -> ".join(cycle + cycle[:1]))
    return lines


def format_notes(graph, substring):
    """Строки о фильтре и о пакетах, которых нет в репозитории."""
    lines = []
    if substring:
        found = ", ".join(graph.excluded) if graph.excluded else "нет"
        lines.append(f"Исключено фильтром '{substring}': {found}")
    if graph.unresolved:
        names = ", ".join(graph.unresolved)
        lines.append(f"Не найдены в репозитории ({len(graph.unresolved)}): "
                     f"{names}")
    return lines


def format_graph(graph, substring):
    """Сформировать полный вывод этапа 3."""
    transitive = graph.transitive()
    names = ", ".join(transitive) if transitive else "нет"
    lines = [f"Пакет: {graph.root}",
             "Граф зависимостей (порядок BFS, [уровень]):"]
    lines.extend(format_edges(graph))
    lines.append(f"Транзитивные зависимости ({len(transitive)}): {names}")
    lines.extend(format_cycles(graph))
    lines.extend(format_notes(graph, substring))
    return lines


def run(config, stream):
    """Построить граф зависимостей пакета и вывести его."""
    source = open_source(config)
    graph = build_graph(source, config.package_name, config.filter_substring)
    print("\n".join(format_graph(graph, config.filter_substring)),
          file=stream)
