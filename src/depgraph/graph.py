"""Построение графа зависимостей обходом в ширину (BFS) с рекурсией.

Источник данных (source) - любой объект с методами has(name) и
children(name) и множеством unresolved. Так один и тот же обход
работает и с индексом Alpine, и с тестовым репозиторием.
"""

from dataclasses import dataclass

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


def is_excluded(name, substring):
    """Проверить, исключает ли фильтр пакет (пустая подстрока - нет)."""
    return bool(substring) and substring in name


class FilteredSource:
    """Источник без пакетов, имя которых содержит подстроку фильтра.

    Исключённые пакеты не попадают в children (а значит, и вся их ветка
    не обходится); их имена запоминаются в excluded.
    """

    def __init__(self, source, substring):
        """Обернуть источник source фильтром по подстроке substring."""
        self.source = source
        self.substring = substring
        self.excluded = set()

    def children(self, name):
        """Вернуть зависимости пакета, кроме исключённых фильтром."""
        result = []
        for child in self.source.children(name):
            if is_excluded(child, self.substring):
                self.excluded.add(child)
            else:
                result.append(child)
        return result


def visit_level(frontier, depth, source, edges, levels):
    """BFS с рекурсией: обойти один уровень и перейти к следующему.

    Args:
        frontier: пакеты текущего уровня (глубина depth).
        depth: расстояние от корня до пакетов frontier.
        source: откуда брать зависимости (метод children).
        edges: результат - пакет -> кортеж его зависимостей.
        levels: пакет -> уровень; служит и списком посещённых пакетов,
            поэтому пакет попадает в обход один раз и циклы не
            приводят к бесконечной рекурсии.
    """
    if not frontier:
        return
    next_level = []
    for name in frontier:
        edges[name] = tuple(source.children(name))
        for child in edges[name]:
            if child not in levels:
                levels[child] = depth + 1
                next_level.append(child)
    visit_level(next_level, depth + 1, source, edges, levels)


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
    filtered = FilteredSource(source, substring)
    edges, levels = {}, {root: 0}
    try:
        visit_level([root], 0, filtered, edges, levels)
    except RecursionError as exc:
        raise RepositoryError(
            "граф зависимостей слишком глубокий для рекурсивного обхода"
        ) from exc
    return DependencyGraph(
        root=root,
        edges=edges,
        levels=levels,
        excluded=tuple(sorted(filtered.excluded)),
        unresolved=tuple(sorted(source.unresolved)),
        cycles=tuple(find_cycles(root, edges)),
    )
