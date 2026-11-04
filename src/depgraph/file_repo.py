"""Тестовый репозиторий: файл описания графа зависимостей.

Формат файла - по одной строке на пакет:

    A: B C
    B: C
    C:

Имя пакета - одна или несколько больших латинских букв. После
двоеточия через пробел перечислены прямые зависимости (список может
быть пустым). Пустые строки и текст после '#' игнорируются.
"""

import re

from depgraph.errors import RepositoryError

LINE_RE = re.compile(r"^([A-Z]+)\s*:(.*)$")
NAME_RE = re.compile(r"^[A-Z]+$")
COMMENT_MARK = "#"


class FileSource:
    """Источник данных, построенный по описанию тестового репозитория.

    Attributes:
        unresolved: пакеты, указанные как зависимости, но не описанные
            в файле.
    """

    def __init__(self, table):
        """Создать источник из словаря 'пакет -> кортеж зависимостей'."""
        self.table = table
        self.unresolved = set()

    def has(self, name):
        """Проверить, описан ли пакет в файле."""
        return name in self.table

    def names(self):
        """Вернуть имена описанных пакетов в порядке файла."""
        return list(self.table)

    def children(self, name):
        """Вернуть прямые зависимости пакета (пустой список, если нет)."""
        dependencies = self.table.get(name, ())
        for dependency in dependencies:
            if dependency not in self.table:
                self.unresolved.add(dependency)
        return list(dependencies)


def parse_line(line, number):
    """Разобрать строку описания; вернуть (имя, зависимости) или None."""
    text = line.split(COMMENT_MARK, maxsplit=1)[0].strip()
    if not text:
        return None
    match = LINE_RE.match(text)
    if not match:
        raise RepositoryError(
            f"строка {number}: ожидается 'ИМЯ: зависимости', "
            f"получено {text!r}"
        )
    dependencies = []
    for token in match.group(2).split():
        if not NAME_RE.match(token):
            raise RepositoryError(
                f"строка {number}: имя пакета {token!r} должно состоять "
                "из больших латинских букв"
            )
        if token not in dependencies:
            dependencies.append(token)
    return match.group(1), tuple(dependencies)


def parse_repo_text(text):
    """Разобрать текст описания и вернуть словарь пакетов.

    Raises:
        RepositoryError: неверный формат, повтор пакета, пустое описание.
    """
    table = {}
    for number, line in enumerate(text.splitlines(), start=1):
        entry = parse_line(line, number)
        if entry is None:
            continue
        name, dependencies = entry
        if name in table:
            raise RepositoryError(
                f"строка {number}: пакет '{name}' описан повторно"
            )
        table[name] = dependencies
    if not table:
        raise RepositoryError("в описании репозитория нет ни одного пакета")
    return table


def load_file_source(path):
    """Загрузить тестовый репозиторий из файла.

    Raises:
        RepositoryError: файл недоступен или содержит ошибки.
    """
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError as exc:
        raise RepositoryError(
            f"не удалось прочитать файл репозитория '{path}': {exc.strerror}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise RepositoryError(
            f"файл репозитория '{path}' должен быть в кодировке UTF-8"
        ) from exc
    try:
        return FileSource(parse_repo_text(text))
    except RepositoryError as exc:
        raise RepositoryError(f"файл '{path}': {exc}") from exc
