"""Исключения приложения."""


class ConfigError(Exception):
    """Ошибка конфигурации.

    Хранит список всех найденных проблем, чтобы пользователь мог
    исправить их за один запуск.
    """

    def __init__(self, problems):
        """Создать исключение.

        Args:
            problems: список текстовых описаний проблем.
        """
        super().__init__("; ".join(problems))
        self.problems = list(problems)
