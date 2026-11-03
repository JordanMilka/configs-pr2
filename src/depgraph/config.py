"""Загрузка и проверка конфигурационного файла в формате YAML."""

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import yaml

from depgraph.errors import ConfigError

PARAM_NAMES = (
    "package_name",
    "repository",
    "test_mode",
    "package_version",
    "ascii_tree",
    "filter_substring",
)
URL_SCHEMES = ("http", "https")
PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
VERSION_RE = re.compile(
    r"^[0-9]+(\.[0-9]+)*[a-z]?"
    r"(_(alpha|beta|pre|rc|cvs|svn|git|hg|p)[0-9]*)*"
    r"(-r[0-9]+)?$"
)


@dataclass(frozen=True)
class Config:
    """Проверенные пользовательские параметры приложения."""

    package_name: str
    repository: str
    test_mode: bool
    package_version: str
    ascii_tree: bool
    filter_substring: str

    def as_pairs(self):
        """Вернуть параметры как список пар (ключ, значение)."""
        return [(name, getattr(self, name)) for name in PARAM_NAMES]


def fail(message):
    """Выбросить ConfigError с одним сообщением."""
    raise ConfigError([message])


def read_yaml(path):
    """Прочитать YAML-файл и вернуть его содержимое.

    Raises:
        ConfigError: файл не найден, недоступен или не является YAML.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError:
        fail(f"файл конфигурации не найден: {path}")
    except OSError as exc:
        fail(f"не удалось прочитать '{path}': {exc.strerror}")
    except UnicodeDecodeError:
        fail(f"файл '{path}' должен быть в кодировке UTF-8")
    except yaml.YAMLError as exc:
        fail(f"некорректный YAML в '{path}': {exc}")


def check_structure(raw):
    """Проверить, что корень - словарь с ровно нужным набором ключей."""
    if not isinstance(raw, dict):
        fail("корень файла должен быть словарём вида 'ключ: значение'")
    problems = [
        f"неизвестный параметр '{key}'"
        for key in raw
        if key not in PARAM_NAMES
    ]
    problems += [
        f"отсутствует обязательный параметр '{name}'"
        for name in PARAM_NAMES
        if name not in raw
    ]
    if problems:
        raise ConfigError(problems)


def require_str(name, value):
    """Убедиться, что значение параметра - строка."""
    if not isinstance(value, str):
        fail(
            f"параметр '{name}' должен быть строкой, получено: "
            f"{value!r} (возьмите значение в кавычки)"
        )
    return value


def check_bool(name, value):
    """Проверить логический параметр (true/false)."""
    if not isinstance(value, bool):
        fail(
            f"параметр '{name}' должен быть логическим (true/false), "
            f"получено: {value!r}"
        )
    return value


def check_package_name(value):
    """Проверить имя пакета."""
    text = require_str("package_name", value)
    if not PACKAGE_NAME_RE.match(text):
        fail(
            f"параметр 'package_name': недопустимое имя {text!r}; "
            "разрешены латинские буквы, цифры и символы . _ + -, "
            "имя должно начинаться с буквы или цифры"
        )
    return text


def check_repo_url(text):
    """Проверить, что значение - HTTP(S) URL."""
    parsed = urlparse(text)
    if parsed.scheme not in URL_SCHEMES or not parsed.netloc:
        fail(
            f"параметр 'repository': {text!r} не является URL "
            "со схемой http или https"
        )
    return text


def check_repo_file(text):
    """Проверить, что значение - путь к существующему читаемому файлу."""
    if not os.path.exists(text):
        fail(f"параметр 'repository': файл не найден: {text}")
    if not os.path.isfile(text):
        fail(f"параметр 'repository': {text} не является файлом")
    if not os.access(text, os.R_OK):
        fail(f"параметр 'repository': нет прав на чтение файла {text}")
    return text


def check_repository(value, test_mode):
    """Проверить URL или путь к файлу в зависимости от режима."""
    text = require_str("repository", value)
    if not text.strip():
        fail("параметр 'repository' не должен быть пустым")
    if test_mode:
        return check_repo_file(text)
    return check_repo_url(text)


def check_version(value):
    """Проверить версию пакета в формате Alpine (например, 1.2.3-r0)."""
    text = require_str("package_version", value)
    if not VERSION_RE.match(text):
        fail(
            f"параметр 'package_version': недопустимая версия {text!r}; "
            "ожидается формат Alpine, например 1.2.3, 1.2.3-r0, 2.0_rc1"
        )
    return text


def check_filter(value):
    """Проверить подстроку фильтрации (может быть пустой)."""
    text = require_str("filter_substring", value)
    if any(char.isspace() for char in text):
        fail(
            "параметр 'filter_substring' не должен содержать "
            "пробельных символов"
        )
    return text


def collect(values, problems, name, checker, *args):
    """Выполнить проверку; результат в values, ошибки - в problems."""
    try:
        values[name] = checker(*args)
    except ConfigError as exc:
        problems.extend(exc.problems)


def validate(raw):
    """Проверить все параметры и вернуть объект Config.

    Raises:
        ConfigError: если найдена хотя бы одна проблема. Параметр
            'repository' не проверяется, если некорректен 'test_mode'.
    """
    check_structure(raw)
    values, problems = {}, []
    collect(values, problems, "package_name",
            check_package_name, raw["package_name"])
    collect(values, problems, "test_mode",
            check_bool, "test_mode", raw["test_mode"])
    if "test_mode" in values:
        collect(values, problems, "repository",
                check_repository, raw["repository"], values["test_mode"])
    collect(values, problems, "package_version",
            check_version, raw["package_version"])
    collect(values, problems, "ascii_tree",
            check_bool, "ascii_tree", raw["ascii_tree"])
    collect(values, problems, "filter_substring",
            check_filter, raw["filter_substring"])
    if problems:
        raise ConfigError(problems)
    return Config(**values)


def load_config(path):
    """Загрузить и проверить конфигурацию из YAML-файла."""
    return validate(read_yaml(path))
