"""Источник обратных зависимостей: кто зависит от данного пакета.

ReverseSource оборачивает обычный источник данных (индекс Alpine или
тестовый репозиторий) и переворачивает все его зависимости. Результат
подходит для того же обхода BFS, что и в graph.build_graph.
"""


class ReverseSource:
    """Источник, в котором дети пакета - пакеты, зависящие от него.

    Attributes:
        unresolved: всегда пусто (в обратном графе нет ненайденных).
    """

    def __init__(self, source):
        """Построить обратные связи по всем пакетам источника.

        Args:
            source: источник с методами names(), children(name), has(name).
        """
        self.source = source
        self.unresolved = set()
        self.reverse = {}
        for name in source.names():
            for child in source.children(name):
                dependents = self.reverse.setdefault(child, [])
                if name not in dependents:
                    dependents.append(name)

    def has(self, name):
        """Проверить, известен ли пакет (описан или упомянут)."""
        return name in self.reverse or self.source.has(name)

    def children(self, name):
        """Вернуть пакеты, которые напрямую зависят от пакета name."""
        return list(self.reverse.get(name, ()))
