"""Текстовое представление графа зависимостей.

format_mermaid строит описание на языке диаграмм Mermaid, format_tree -
ASCII-дерево. Оба принимают DependencyGraph из graph.build_graph.
"""

import itertools
import re

SAFE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
RESERVED_IDS = frozenset((
    "end", "graph", "subgraph", "flowchart", "style", "class",
    "classdef", "click", "default", "linkstyle", "direction",
))
GENERATED_PREFIX = "n"
INDENT = "    "
HEADER = "graph TD"
ROOT_CLASS = "root"
MISSING_CLASS = "missing"
CLASS_STYLES = {
    ROOT_CLASS: "fill:#d0e6ff,stroke:#2b5c99,stroke-width:2px",
    MISSING_CLASS: "stroke-dasharray:5 5",
}
BRANCH_MIDDLE = "|-- "
BRANCH_LAST = "`-- "
PIPE = "|   "
BLANK = "    "
MARK_REPEAT = " (*)"
MARK_CYCLE = " (цикл)"
LEGEND_REPEAT = "(*) - зависимости этого пакета показаны выше"
LEGEND_CYCLE = "(цикл) - пакет уже есть среди его предков"


def is_safe_id(name):
    """Проверить, что имя годится в идентификаторы узлов Mermaid."""
    return bool(SAFE_ID_RE.match(name)) and name.lower() not in RESERVED_IDS


def assign_ids(names):
    """Сопоставить именам идентификаторы узлов Mermaid.

    Подходящие имена используются как есть, остальные (с дефисом,
    точкой, двоеточием, служебные слова) получают n0, n1, ...
    """
    ids = {name: name for name in names if is_safe_id(name)}
    used = set(ids.values())
    generated = (f"{GENERATED_PREFIX}{index}"
                 for index in itertools.count())
    for name in names:
        if name not in ids:
            ids[name] = next(item for item in generated
                             if item not in used)
            used.add(ids[name])
    return ids


def escape_label(name):
    """Экранировать кавычки в подписи узла."""
    return name.replace('"', "#quot;")


def declaration_lines(graph, ids):
    """Объявления узлов: с подписью, если идентификатор отличается."""
    connected = {name for name, kids in graph.edges.items() if kids}
    for kids in graph.edges.values():
        connected.update(kids)
    return [
        f'{INDENT}{ids[name]}["{escape_label(name)}"]'
        for name in graph.edges
        if ids[name] != name or name not in connected
    ]


def edge_lines(graph, ids):
    """Рёбра 'пакет --> зависимость' в порядке обхода BFS."""
    return [
        f"{INDENT}{ids[name]} --> {ids[child]}"
        for name, children in graph.edges.items()
        for child in children
    ]


def class_lines(graph, ids):
    """Стили: корневой пакет и пакеты, которых нет в репозитории."""
    missing = [ids[name] for name in graph.unresolved
               if name in graph.edges]
    used = {ROOT_CLASS: [ids[graph.root]], MISSING_CLASS: missing}
    lines = []
    for class_name, members in used.items():
        if members:
            lines.append(f"{INDENT}classDef {class_name} "
                         f"{CLASS_STYLES[class_name]}")
            lines.append(f"{INDENT}class {','.join(members)} {class_name}")
    return lines


def format_mermaid(graph):
    """Сформировать описание графа на языке диаграмм Mermaid."""
    ids = assign_ids(list(graph.edges))
    lines = [HEADER]
    lines.extend(declaration_lines(graph, ids))
    lines.extend(edge_lines(graph, ids))
    lines.extend(class_lines(graph, ids))
    return lines


def tree_marker(graph, child, ancestors, expanded):
    """Вернуть пометку для узла дерева и признак, нужно ли раскрывать его."""
    if child in ancestors:
        return MARK_CYCLE, False
    if not graph.edges.get(child):
        return "", False
    if child in expanded:
        return MARK_REPEAT, False
    return "", True


def format_tree(graph):
    """Сформировать ASCII-дерево зависимостей (обход без рекурсии).

    Зависимости пакета показываются один раз, при первой встрече;
    повтор помечается (*), возврат к предку - (цикл).
    """
    lines = [graph.root]
    expanded, path = {graph.root}, [graph.root]
    ancestors = {graph.root}
    stack = [["", list(graph.edges[graph.root]), 0]]
    marks = set()
    while stack:
        frame = stack[-1]
        prefix, children, position = frame
        if position == len(children):
            stack.pop()
            ancestors.discard(path.pop())
            continue
        frame[2] += 1
        child = children[position]
        last = position == len(children) - 1
        mark, descend = tree_marker(graph, child, ancestors, expanded)
        marks.add(mark)
        lines.append(prefix + (BRANCH_LAST if last else BRANCH_MIDDLE)
                     + child + mark)
        if descend:
            expanded.add(child)
            path.append(child)
            ancestors.add(child)
            stack.append([prefix + (BLANK if last else PIPE),
                          list(graph.edges[child]), 0])
    return lines + tree_legend(marks)


def tree_legend(marks):
    """Пояснения к использованным пометкам дерева."""
    legend = []
    if MARK_REPEAT in marks:
        legend.append(LEGEND_REPEAT)
    if MARK_CYCLE in marks:
        legend.append(LEGEND_CYCLE)
    return legend
