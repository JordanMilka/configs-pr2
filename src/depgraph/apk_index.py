"""Разбор индекса пакетов Alpine Linux (файл APKINDEX).

Индекс - текст из записей, разделённых пустой строкой. Каждая строка
записи имеет вид 'X:значение', где X - однобуквенное поле:
P - имя пакета, V - версия, D - зависимости, p - предоставляемое.
"""

import re
from dataclasses import dataclass

from depgraph.errors import RepositoryError

FIELD_RE = re.compile(r"^([A-Za-z]):(.*)$")
RECORD_SPLIT_RE = re.compile(r"\n[ \t]*\n")
DEPENDENCY_RE = re.compile(
    r"^(?P<name>[^<>=~]+)(?:(?P<operator>[<>=~]+)(?P<version>.+))?$"
)
CONFLICT_PREFIX = "!"
NAME_FIELD = "P"
VERSION_FIELD = "V"
DEPENDS_FIELD = "D"
PROVIDES_FIELD = "p"


@dataclass(frozen=True)
class Dependency:
    """Зависимость пакета.

    Attributes:
        name: имя пакета или виртуальное имя (например, so:libc...).
        operator: оператор сравнения версий (=, >=, <, ~ и т.п.) или "".
        version: версия из ограничения или "".
        raw: исходная запись в индексе.
    """

    name: str
    operator: str
    version: str
    raw: str


@dataclass(frozen=True)
class Package:
    """Запись о пакете в индексе."""

    name: str
    version: str
    depends: tuple
    provides: tuple


def parse_dependency(token):
    """Разобрать одну запись зависимости, например 'musl>=1.2.5'."""
    match = DEPENDENCY_RE.match(token)
    if not match:
        return Dependency(token, "", "", token)
    return Dependency(
        name=match.group("name"),
        operator=match.group("operator") or "",
        version=match.group("version") or "",
        raw=token,
    )


def parse_depends(value):
    """Разобрать значение поля D. Конфликты (!имя) пропускаются."""
    tokens = [
        token
        for token in value.split()
        if not token.startswith(CONFLICT_PREFIX)
    ]
    return tuple(parse_dependency(token) for token in tokens)


def parse_record(block):
    """Преобразовать блок текста записи в словарь 'поле -> значение'."""
    fields = {}
    for line in block.splitlines():
        match = FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def record_to_package(fields):
    """Создать Package из полей записи; None, если нет имени или версии."""
    name = fields.get(NAME_FIELD)
    version = fields.get(VERSION_FIELD)
    if not name or not version:
        return None
    return Package(
        name=name,
        version=version,
        depends=parse_depends(fields.get(DEPENDS_FIELD, "")),
        provides=tuple(fields.get(PROVIDES_FIELD, "").split()),
    )


def parse_index(text):
    """Разобрать текст APKINDEX и вернуть список пакетов."""
    normalized = text.replace("\r\n", "\n")
    packages = []
    for block in RECORD_SPLIT_RE.split(normalized):
        package = record_to_package(parse_record(block))
        if package:
            packages.append(package)
    return packages


def find_package(packages, name, version):
    """Найти пакет с точным совпадением имени и версии.

    Raises:
        RepositoryError: пакет или его версия отсутствуют в индексе.
    """
    candidates = [pkg for pkg in packages if pkg.name == name]
    if not candidates:
        raise RepositoryError(f"пакет '{name}' не найден в репозитории")
    for package in candidates:
        if package.version == version:
            return package
    available = ", ".join(sorted(pkg.version for pkg in candidates))
    raise RepositoryError(
        f"версия '{version}' пакета '{name}' не найдена; "
        f"доступные версии: {available}"
    )
