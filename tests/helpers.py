"""Вспомогательные функции для тестов."""

import json
import os

VALID_CONFIG = {
    "package_name": "busybox",
    "repository": "https://dl-cdn.alpinelinux.org/alpine/v3.20/main",
    "test_mode": False,
    "package_version": "1.36.1-r29",
    "ascii_tree": True,
    "filter_substring": "musl",
}


def make_config(**overrides):
    """Вернуть корректный словарь конфигурации с заменами."""
    data = dict(VALID_CONFIG)
    data.update(overrides)
    return data


def dump_value(value):
    """Преобразовать значение Python в скаляр YAML."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def write_yaml(directory, data, name="config.yaml"):
    """Записать словарь в YAML-файл и вернуть путь к нему."""
    path = os.path.join(directory, name)
    lines = [f"{key}: {dump_value(val)}" for key, val in data.items()]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def write_text(directory, text, name="config.yaml", mode="w"):
    """Записать текст (или байты при mode='wb') в файл."""
    path = os.path.join(directory, name)
    kwargs = {} if "b" in mode else {"encoding": "utf-8"}
    with open(path, mode, **kwargs) as handle:
        handle.write(text)
    return path
