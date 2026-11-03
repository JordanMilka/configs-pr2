"""Вспомогательные функции для тестов."""

import os

import yaml

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


def write_yaml(directory, data, name="config.yaml"):
    """Записать словарь в YAML-файл и вернуть путь к нему."""
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True)
    return path


def write_text(directory, text, name="config.yaml", mode="w"):
    """Записать текст (или байты при mode='wb') в файл."""
    path = os.path.join(directory, name)
    kwargs = {} if "b" in mode else {"encoding": "utf-8"}
    with open(path, mode, **kwargs) as handle:
        handle.write(text)
    return path
