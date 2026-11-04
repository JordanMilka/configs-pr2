"""Источник данных для графа: индекс пакетов Alpine Linux."""

from depgraph.apk_index import parse_dependency


class AlpineSource:
    """Сопоставляет зависимости пакетам индекса Alpine.

    Зависимость может называть пакет напрямую (musl) или виртуальное
    имя, которое пакет предоставляет (so:libc.musl-x86_64.so.1,
    cmd:sh). Прямое имя пакета важнее виртуального; если пакетов с
    одним именем или поставщиков несколько, берётся первый в индексе.

    Attributes:
        unresolved: имена зависимостей, которых нет в индексе.
    """

    def __init__(self, packages, pinned):
        """Создать источник.

        Args:
            packages: список Package из индекса.
            pinned: запись корневого пакета с выбранной версией.
        """
        self.pinned = pinned
        self.unresolved = set()
        self.by_name = {}
        self.providers = {}
        for package in packages:
            self.by_name.setdefault(package.name, []).append(package)
            for token in package.provides:
                name = parse_dependency(token).name
                self.providers.setdefault(name, []).append(package)

    def lookup(self, name):
        """Вернуть запись пакета по имени или None."""
        if name == self.pinned.name:
            return self.pinned
        candidates = self.by_name.get(name)
        return candidates[0] if candidates else None

    def has(self, name):
        """Проверить, есть ли пакет с таким именем."""
        return self.lookup(name) is not None

    def resolve(self, dependency):
        """Найти пакет, удовлетворяющий зависимости, или None."""
        candidates = self.by_name.get(dependency.name)
        candidates = candidates or self.providers.get(dependency.name)
        return candidates[0] if candidates else None

    def children(self, name):
        """Вернуть имена пакетов - прямых зависимостей пакета name.

        Зависимость, которая разрешается в сам пакет (он сам
        предоставляет это имя), пропускается. Неразрешённые зависимости
        возвращаются под своим именем и запоминаются в unresolved.
        """
        package = self.lookup(name)
        if package is None:
            return []
        result = []
        for dependency in package.depends:
            target = self.resolve(dependency)
            child = target.name if target else dependency.name
            if target is None:
                self.unresolved.add(child)
            if child != name and child not in result:
                result.append(child)
        return result
