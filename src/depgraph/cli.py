"""Интерфейс командной строки."""

import argparse
import sys

from depgraph.apk_index import find_package
from depgraph.config import load_config
from depgraph.errors import ConfigError, RepositoryError
from depgraph.repository import load_packages

DEFAULT_CONFIG = "config.yaml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_DATA_ERROR = 3


def build_parser():
    """Создать парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Визуализация графа зависимостей пакетов Alpine.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG,
        help=f"путь к YAML-файлу конфигурации (по умолчанию "
        f"{DEFAULT_CONFIG})",
    )
    return parser


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


def report_config_errors(error, stream):
    """Вывести список проблем конфигурации."""
    print("Ошибка конфигурации:", file=stream)
    for problem in error.problems:
        print(f"  - {problem}", file=stream)


def main(argv=None):
    """Точка входа. Возвращает код завершения процесса."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_config_errors(error, sys.stderr)
        return EXIT_CONFIG_ERROR
    try:
        package = fetch_package(config)
    except RepositoryError as error:
        print(f"Ошибка получения данных: {error}", file=sys.stderr)
        return EXIT_DATA_ERROR
    print("\n".join(format_dependencies(package)), file=sys.stdout)
    return EXIT_OK
