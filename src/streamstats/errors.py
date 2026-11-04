"""Общая ошибка анализатора и ошибки отдельных полей события."""


class StreamStatsError(Exception):
    """Базовое исключение для ошибок обработки событий."""

    def __init__(self, msg):
        """Инициализировать сообщение ошибки."""
        self.msg = msg
        super().__init__(self.msg)


class UnsupportedFormatError(StreamStatsError):
    """Запрошенный формат не поддерживается парсерами."""


class CLIConfigError(StreamStatsError):
    """Параметры запуска несовместимы или могут повредить входные файлы."""


class InvalidEventError(StreamStatsError):
    """Неверная структура события или повреждённая запись."""

    def __init__(self, msg):
        super().__init__(msg)


class InvalidTimestampError(StreamStatsError):
    """Временная метка не может быть разобрана или сравнена."""

    def __init__(self, msg):
        super().__init__(msg)


class InvalidLevelError(StreamStatsError):
    """Уровень события не входит в список разрешённых."""

    def __init__(self, msg):
        super().__init__(msg)


class InvalidSourceError(StreamStatsError):
    """Источник события не является непустой строкой."""

    def __init__(self, msg):
        super().__init__(msg)


class InvalidMessageError(StreamStatsError):
    """Сообщение события не является строкой."""

    def __init__(self, msg):
        super().__init__(msg)
