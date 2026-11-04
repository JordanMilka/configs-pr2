"""Этап 2: сбор данных - прямые зависимости пакета Alpine."""

from depgraph.apk_index import find_package
from depgraph.errors import RepositoryError
from depgraph.repository import load_packages

SUMMARY = "этап 2: вывести прямые зависимости пакета заданной версии"


def fetch_package(config):
    """Получить из репозитория запись о пакете заданной версии.

    Raises:
        RepositoryError: тестовый режим, ошибка сети, нет пакета/версии.
    """
    if config.test_mode:
        raise RepositoryError(
            "работа с тестовым репозиторием будет добавлена на этапе 3"
        )
    packages = load_packages(config.repository)
    return find_package(
        packages, config.package_name, config.package_version
    )


def format_dependencies(package):
    """Сформировать строки вывода прямых зависимостей пакета."""
    lines = [f"Пакет: {package.name} {package.version}"]
    if not package.depends:
        lines.append("Прямые зависимости: нет")
        return lines
    lines.append(f"Прямые зависимости ({len(package.depends)}):")
    lines.extend(f"  {dep.raw}" for dep in package.depends)
    return lines


def run(config, stream):
    """Вывести прямые зависимости пакета, указанного в конфигурации."""
    package = fetch_package(config)
    print("\n".join(format_dependencies(package)), file=stream)
