"""Этап 1: вывод параметров, настроенных пользователем."""

from depgraph.config import PARAM_NAMES

SUMMARY = "этап 1: вывести параметры конфигурации в формате ключ-значение"


def format_value(value):
    """Преобразовать значение параметра в строку для вывода."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if not value:
        return '""'
    return str(value)


def run(config, stream):
    """Вывести все параметры конфигурации строками 'ключ: значение'."""
    for name in PARAM_NAMES:
        value = format_value(getattr(config, name))
        print(f"{name}: {value}", file=stream)
