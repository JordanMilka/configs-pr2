"""Построение графа зависимостей обходом в ширину (BFS) с рекурсией.

Источник данных (source) - любой объект с методами has(name) и
children(name) и множеством unresolved. Так один и тот же обход
работает и с индексом Alpine, и с тестовым репозиторием.
"""

from dataclasses import dataclass, field

from depgraph.errors import RepositoryError


@dataclass(frozen=True)
class DependencyGraph:
    """Построенный граф зависимостей.

    Attributes:
        root: имя корневого пакета.
        edges: имя -> кортеж прямых зависимостей; порядок ключей
            совпадает с порядком обхода BFS.
        levels: имя -> расстояние от корня (уровень BFS).
        excluded: имена, исключённые подстрокой фильтра.
        unresolved: имена, которых нет в репозитории.
        cycles: найденные циклы; каждый - кортеж имён без повтора.
    """

    root: str
    edges: dict
    levels: dict
    excluded: tuple
    unresolved: tuple
    cycles: tuple

    def transitive(self):
        """Вернуть все достижимые пакеты, кроме корня, в порядке BFS."""
        return [name for name in self.edges if name != self.root]


@dataclass
class WalkState:
    """Изменяемое состояние обхода, общее для всех уровней BFS."""

    source: object
    substring: str
    edges: dict = field(default_factory=dict)
    levels: dict = field(default_factory=dict)
    excluded: set = field(default_factory=set)


def is_excluded(name, substring):
    """Проверить, исключает ли фильтр пакет (пустая подстрока - нет)."""
    return bool(substring) and substring in name


def expand(name, depth, state, next_level):
    """Обработать один пакет: записать его рёбра и найти новые вершины.

    Новые вершины добавляются в next_level, их уровень - depth + 1.
    """
    children = []
    for child in state.source.children(name):
        if is_excluded(child, state.substring):
            state.excluded.add(child)
            continue
        children.append(child)
        if child not in state.levels:
            state.levels[child] = depth + 1
            next_level.append(child)
    state.edges[name] = tuple(children)


def visit_level(frontier, depth, state):
    """Обойти один уровень BFS и рекурсивно перейти к следующему.

    Уже посещённые вершины повторно не добавляются, поэтому циклические
    зависимости не приводят к бесконечной рекурсии.
    """
    if not frontier:
        return
    next_level = []
    for name in frontier:
        expand(name, depth, state, next_level)
    visit_level(next_level, depth + 1, state)


def add_cycle(cycles, seen, nodes):
    """Добавить цикл в список, приведя его к каноническому виду."""
    start = nodes.index(min(nodes))
    canonical = tuple(nodes[start:] + nodes[:start])
    if canonical not in seen:
        seen.add(canonical)
        cycles.append(canonical)


def find_cycles(root, edges):
    """Найти циклы обходом в глубину (без рекурсии).

    Для каждого обратного ребра находится один цикл; одинаковые циклы,
    начатые с разных вершин, считаются одним.
    """
    cycles, seen = [], set()
    path, on_path, done = [root], {root}, set()
    stack = [iter(edges.get(root, ()))]
    while stack:
        child = next(stack[-1], None)
        if child is None:
            stack.pop()
            node = path.pop()
            on_path.discard(node)
            done.add(node)
        elif child in on_path:
            add_cycle(cycles, seen, path[path.index(child):])
        elif child not in done:
            path.append(child)
            on_path.add(child)
            stack.append(iter(edges.get(child, ())))
    return cycles


def check_root(source, root, substring):
    """Проверить, что корневой пакет существует и не исключён фильтром.

    Raises:
        RepositoryError: пакет исключён фильтром или не найден.
    """
    if is_excluded(root, substring):
        raise RepositoryError(
            f"корневой пакет '{root}' содержит подстроку фильтра "
            f"'{substring}' и исключён из анализа"
        )
    if not source.has(root):
        raise RepositoryError(f"пакет '{root}' не найден в репозитории")


def build_graph(source, root, substring):
    """Построить граф транзитивных зависимостей пакета root.

    Args:
        source: источник данных (см. описание модуля).
        root: имя корневого пакета.
        substring: пакеты, имя которых содержит её, не учитываются
            вместе со всеми своими зависимостями; пустая - без фильтра.

    Raises:
        RepositoryError: нет пакета, пакет исключён или граф слишком
            глубокий для рекурсивного обхода.
    """
    check_root(source, root, substring)
    state = WalkState(source, substring)
    state.levels[root] = 0
    try:
        visit_level([root], 0, state)
    except RecursionError as exc:
        raise RepositoryError(
            "граф зависимостей слишком глубокий для рекурсивного обхода"
        ) from exc
    return DependencyGraph(
        root=root,
        edges=state.edges,
        levels=state.levels,
        excluded=tuple(sorted(state.excluded)),
        unresolved=tuple(sorted(source.unresolved)),
        cycles=tuple(find_cycles(root, state.edges)),
    )
