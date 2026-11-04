"""Интерфейс командной строки: отдельная команда для каждого этапа."""

import argparse
import sys

from depgraph import stage1, stage2, stage3, stage4, stage5
from depgraph.config import load_config
from depgraph.errors import ConfigError, RepositoryError

DEFAULT_CONFIG = "config.yaml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_DATA_ERROR = 3
STAGES = {
    "stage1": stage1,
    "stage2": stage2,
    "stage3": stage3,
    "stage4": stage4,
    "stage5": stage5,
}


def build_common_parser():
    """Создать родительский парсер с опциями, общими для всех этапов."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG,
        help=f"путь к YAML-файлу конфигурации (по умолчанию "
        f"{DEFAULT_CONFIG})",
    )
    return common


def build_parser():
    """Создать парсер аргументов с командами этапов."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Визуализация графа зависимостей пакетов Alpine.",
    )
    subparsers = parser.add_subparsers(
        dest="command", metavar="КОМАНДА", required=True
    )
    common = build_common_parser()
    for name, stage in STAGES.items():
        subparsers.add_parser(
            name,
            parents=[common],
            help=stage.SUMMARY,
            description=stage.SUMMARY,
        )
    return parser


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
        STAGES[args.command].run(config, sys.stdout)
    except RepositoryError as error:
        print(f"Ошибка получения данных: {error}", file=sys.stderr)
        return EXIT_DATA_ERROR
    return EXIT_OK
