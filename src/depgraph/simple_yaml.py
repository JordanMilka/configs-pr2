"""Минимальный разбор плоского YAML без сторонних библиотек.

Поддерживается подмножество YAML: строки 'ключ: значение', комментарии,
значения null, true/false, целые и дробные числа, строки в обычном виде,
в двойных кавычках (с JSON-экранированием) и в одинарных кавычках.
Вложенные структуры, списки и многострочные значения не поддерживаются.
"""

import json
import re

from depgraph.errors import ConfigError

QUOTES = ('"', "'")
UNSUPPORTED_START = "[{&*|>!%@`"
PAIR_RE = re.compile(r"^([^\s:#][^:]*?)\s*:(?:\s+(.*))?$")
DOUBLE_RE = re.compile(r'^"(?:[^"\\]|\\.)*"$')
SINGLE_RE = re.compile(r"^'(?:[^']|'')*'$")
INT_RE = re.compile(r"^[-+]?[0-9]+$")
FLOAT_RE = re.compile(
    r"^[-+]?([0-9]+\.[0-9]*|\.[0-9]+)([eE][-+]?[0-9]+)?$"
)
KEYWORDS = {"null": None, "~": None, "true": True, "false": False}


def syntax_error(number, message):
    """Выбросить ConfigError с указанием номера строки."""
    raise ConfigError([f"строка {number}: {message}"])


def advance_quote(quote, escaped, char):
    """Вернуть состояние (quote, escaped) после очередного символа.

    quote - открытая кавычка или None, escaped - предыдущий символ был
    обратной косой чертой внутри двойных кавычек.
    """
    if escaped:
        return quote, False
    if char == "\\" and quote == '"':
        return quote, True
    if char == quote:
        return None, False
    return quote, False


def is_comment_start(text, index):
    """Проверить, что символ text[index] начинает комментарий."""
    if text[index] != "#":
        return False
    return not index or text[index - 1].isspace()


def strip_comment(text):
    """Отрезать комментарий '# ...', не затрагивая текст в кавычках."""
    quote, escaped = None, False
    for index, char in enumerate(text):
        if quote:
            quote, escaped = advance_quote(quote, escaped, char)
        elif char in QUOTES:
            quote = char
        elif is_comment_start(text, index):
            return text[:index]
    return text


def split_pair(text, number):
    """Разделить строку на ключ и необработанное значение."""
    match = PAIR_RE.match(text)
    if not match:
        syntax_error(number, "ожидается строка вида 'ключ: значение'")
    return match.group(1).strip(), (match.group(2) or "").strip()


def parse_double(raw, number):
    """Разобрать строку в двойных кавычках."""
    if not DOUBLE_RE.match(raw):
        syntax_error(number, "незакрытая кавычка или лишние символы")
    try:
        return json.loads(raw)
    except ValueError:
        syntax_error(number, f"недопустимая escape-последовательность: {raw}")


def parse_single(raw, number):
    """Разобрать строку в одинарных кавычках."""
    if not SINGLE_RE.match(raw):
        syntax_error(number, "незакрытая кавычка или лишние символы")
    return raw[1:-1].replace("''", "'")


def convert_plain(raw):
    """Преобразовать значение без кавычек в None, bool, число или строку."""
    lowered = raw.lower()
    if lowered in KEYWORDS:
        return KEYWORDS[lowered]
    if INT_RE.match(raw):
        return int(raw)
    if FLOAT_RE.match(raw):
        return float(raw)
    return raw


def parse_scalar(raw, number):
    """Разобрать значение параметра."""
    if not raw:
        return None
    if raw[0] == '"':
        return parse_double(raw, number)
    if raw[0] == "'":
        return parse_single(raw, number)
    if raw[0] in UNSUPPORTED_START:
        syntax_error(number, f"неподдерживаемая конструкция YAML: {raw}")
    return convert_plain(raw)


def parse_yaml(text):
    """Разобрать текст и вернуть словарь, либо None для пустого файла."""
    result = {}
    for number, line in enumerate(text.splitlines(), start=1):
        content = strip_comment(line).rstrip()
        if not content.strip():
            continue
        if content[:1].isspace():
            syntax_error(number, "отступы и вложенность не поддерживаются")
        key, raw = split_pair(content, number)
        if key in result:
            syntax_error(number, f"повторяющийся ключ '{key}'")
        result[key] = parse_scalar(raw, number)
    return result or None
