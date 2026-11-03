"""Тесты встроенного разбора плоского YAML."""

import unittest

from depgraph.errors import ConfigError
from depgraph.simple_yaml import parse_yaml


class ParseValuesTests(unittest.TestCase):
    """Разбор корректных значений."""

    def test_plain_scalars(self):
        """Значения без кавычек."""
        data = parse_yaml("a: true\nb: False\nc: 5\nd: 1.5\ne: null\nf: x")
        self.assertIs(data["a"], True)
        self.assertIs(data["b"], False)
        self.assertEqual(data["c"], 5)
        self.assertEqual(data["d"], 1.5)
        self.assertIsNone(data["e"])
        self.assertEqual(data["f"], "x")

    def test_version_like_strings(self):
        """Версии и URL остаются строками."""
        data = parse_yaml("v: 1.36.1-r29\nu: https://h.org/a#b\nr: 2.0_rc1")
        self.assertEqual(data["v"], "1.36.1-r29")
        self.assertEqual(data["u"], "https://h.org/a#b")
        self.assertEqual(data["r"], "2.0_rc1")

    def test_quoted_strings(self):
        """Строки в кавычках не преобразуются в числа и bool."""
        data = parse_yaml("a: \"1.10\"\nb: 'true'\nc: ''\nd: 'it''s'")
        self.assertEqual(data["a"], "1.10")
        self.assertEqual(data["b"], "true")
        self.assertEqual(data["c"], "")
        self.assertEqual(data["d"], "it's")

    def test_escapes_and_unicode(self):
        """Escape-последовательности и кириллица в двойных кавычках."""
        data = parse_yaml('a: "x\\ty"\nb: "имя"\nc: "q\\"q"')
        self.assertEqual(data["a"], "x\ty")
        self.assertEqual(data["b"], "имя")
        self.assertEqual(data["c"], 'q"q')

    def test_comments_and_blank_lines(self):
        """Комментарии и пустые строки игнорируются."""
        text = "# заголовок\n\na: 1  # хвост\nb: \"x # y\"\n"
        data = parse_yaml(text)
        self.assertEqual(data, {"a": 1, "b": "x # y"})

    def test_empty_inputs(self):
        """Пустой текст и только комментарии дают None."""
        self.assertIsNone(parse_yaml(""))
        self.assertIsNone(parse_yaml("# только комментарий\n"))

    def test_empty_value_is_none(self):
        """Ключ без значения даёт None."""
        self.assertEqual(parse_yaml("a:"), {"a": None})


class ParseErrorTests(unittest.TestCase):
    """Некорректный ввод."""

    def assert_error(self, text, fragment):
        """Проверить, что разбор падает с сообщением про fragment."""
        with self.assertRaises(ConfigError) as ctx:
            parse_yaml(text)
        self.assertIn(fragment, ctx.exception.problems[0])

    def test_no_colon(self):
        """Строка без двоеточия."""
        self.assert_error("just text", "ключ: значение")

    def test_url_without_key(self):
        """Строка, начинающаяся с URL, - не пара ключ-значение."""
        self.assert_error("http://x", "ключ: значение")

    def test_indentation(self):
        """Отступы не поддерживаются."""
        self.assert_error("a:\n  b: 1", "отступы")

    def test_list_item(self):
        """Элементы списка не поддерживаются."""
        self.assert_error("- a", "ключ: значение")

    def test_flow_collection(self):
        """Значения [..] и {..} не поддерживаются."""
        self.assert_error("a: [1, 2]", "неподдерживаемая")
        self.assert_error("a: {b: 1}", "неподдерживаемая")

    def test_unclosed_quote(self):
        """Незакрытая кавычка."""
        self.assert_error('a: "abc', "кавычка")
        self.assert_error("a: 'abc", "кавычка")

    def test_trailing_after_quote(self):
        """Лишние символы после закрывающей кавычки."""
        self.assert_error('a: "abc" tail', "кавычка")

    def test_bad_escape(self):
        """Недопустимая escape-последовательность."""
        self.assert_error('a: "\\q"', "escape")

    def test_duplicate_key(self):
        """Повторяющийся ключ."""
        self.assert_error("a: 1\na: 2", "повторяющийся")

    def test_error_has_line_number(self):
        """Сообщение содержит номер строки."""
        self.assert_error("a: 1\nbad line", "строка 2")


if __name__ == "__main__":
    unittest.main()
