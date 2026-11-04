from dataclasses import dataclass


@dataclass
class Event:
    """Модель события: timestamp, level, source, message."""
    num: int
    timestamp: str
    level: str
    source: str
    message: str


@dataclass
class InvalidRecord:
    """Номер строки и причина пропуска некорректной записи."""
    num: int
    reason: str
