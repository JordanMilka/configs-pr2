"""Интерфейс командной строки."""

import argparse
import sys

from depgraph.config import load_config
from depgraph.errors import ConfigError

DEFAULT_CONFIG = "config.yaml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2


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


def format_value(value):
    """Преобразовать значение параметра в строку для вывода."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if not value:
        return '""'
    return str(value)


def print_params(config, stream):
    """Вывести параметры в формате 'ключ: значение'."""
    for key, value in config.as_pairs():
        print(f"{key}: {format_value(value)}", file=stream)


def report_errors(error, stream):
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
        report_errors(error, sys.stderr)
        return EXIT_CONFIG_ERROR
    print_params(config, sys.stdout)
    return EXIT_OK
