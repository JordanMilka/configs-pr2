"""Разбор вывода 'apk dot' (формат Graphviz) для сравнения графов."""

import re
from dataclasses import dataclass

EDGE_RE = re.compile(r'^\s*"([^"]+)"\s*->\s*"([^"]+)"\[(.*)\];\s*$')
LABEL_RE = re.compile(r'label="([^"]*)"')
NODE_RE = re.compile(r"^(.+)-(\d[^-]*-r\d+)$")
RED_MARK = "color=red"


@dataclass(frozen=True)
class DotEdge:
    """Ребро графа apk dot.

    Attributes:
        source: пакет-источник вместе с версией (curl-8.14.1-r2).
        target: пакет-цель вместе с версией.
        label: зависимость, из-за которой нарисовано ребро ("" - прямая).
        red: ребро нарисовано красным цветом.
    """

    source: str
    target: str
    label: str
    red: bool


def split_node(node):
    """Разделить 'имя-версия' на имя и версию."""
    match = NODE_RE.match(node)
    return match.group(1), match.group(2)


def parse_dot(text):
    """Разобрать вывод apk dot и вернуть список рёбер DotEdge."""
    edges = []
    for line in text.splitlines():
        match = EDGE_RE.match(line)
        if match:
            source, target, attributes = match.groups()
            label = LABEL_RE.search(attributes)
            edges.append(DotEdge(
                source, target,
                label.group(1) if label else "",
                RED_MARK in attributes,
            ))
    return edges


def name_pairs(edges):
    """Множество пар (имя источника, имя цели) без версий."""
    return {(split_node(edge.source)[0], split_node(edge.target)[0])
            for edge in edges}


def node_names(edges):
    """Множество имён пакетов, встречающихся в рёбрах."""
    return {name for pair in name_pairs(edges) for name in pair}


def versions(edges):
    """Словарь 'имя пакета -> версия' по узлам графа."""
    result = {}
    for edge in edges:
        for node in (edge.source, edge.target):
            name, version = split_node(node)
            result[name] = version
    return result


def reachable_pairs(pairs, root, excluded=()):
    """Рёбра, достижимые из root, если убрать пакеты excluded."""
    allowed = {pair for pair in pairs
               if not set(pair) & set(excluded)}
    children = {}
    for source, target in allowed:
        children.setdefault(source, set()).add(target)
    seen, todo = {root}, [root]
    while todo:
        for child in children.get(todo.pop(), ()):
            if child not in seen:
                seen.add(child)
                todo.append(child)
    return {pair for pair in allowed if pair[0] in seen}
