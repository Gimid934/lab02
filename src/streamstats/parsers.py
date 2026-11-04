"""Потоковое чтение CSV и JSONL."""
import csv
import json
from datetime import datetime

from streamstats.errors import (
    InvalidEventError,
    InvalidLevelError,
    InvalidMessageError,
    InvalidSourceError,
    InvalidTimestampError,
    StreamStatsError,
    UnsupportedFormatError,
)
from streamstats.models import Event, InvalidRecord

FIELDS_LIST = ["timestamp", "level", "source", "message"]
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
FIELDS_SET: set = set(FIELDS_LIST)


def parse_timestamp(data_s: str) -> datetime:
    """Разобрать ISO-время, включая UTC с суффиксом Z в Python 3.10."""
    if isinstance(data_s, str) and data_s.endswith("Z"):
        data_s = data_s[:-1] + "+00:00"
    return datetime.fromisoformat(data_s)


def time_val(data_s: str) -> bool:
    """Вернуть True, если значение можно разобрать как ISO-время."""
    try:
        parse_timestamp(data_s)
        return True
    except (ValueError, TypeError):
        return False


def level_val(lvl_s: str) -> bool:
    """Проверить, что уровень входит в список DEBUG, INFO, WARNING, ERROR, CRITICAL."""
    return lvl_s in LEVELS


def source_val(source_s: str) -> bool:
    """Проверить, что источник является непустой строкой."""
    return type(source_s) is str and source_s != ''


def message_val(msg_s: str) -> bool:
    """Проверить тип сообщения; пустая строка разрешена."""
    return type(msg_s) is str


def validate(num: int, record: str, **kwargs):
    """Проверить обязательные поля записи и вызвать ошибку при нарушении.

    num — номер строки, record — текст записи для сообщения об ошибке.
    Поля события передаются именованными аргументами. При успехе возвращает None.
    """
    if not FIELDS_SET.issubset(set(kwargs.keys())):
        raise InvalidEventError(f"{num} Line misses required fields: {record}")
    if not time_val(kwargs["timestamp"]):
        raise InvalidTimestampError(f"{num} Incorrect timestamp in line: {record}")
    if not level_val(kwargs["level"]):
        raise InvalidLevelError(f"{num} Incorrect level in line: {record}")
    if not source_val(kwargs["source"]):
        raise InvalidSourceError(f"{num} Incorrect source in line: {record}")
    if not message_val(kwargs["message"]):
        raise InvalidMessageError(f"{num} Incorrect message in line: {record}")


def parse_csv(path: str, skip: bool):
    """Читать CSV с заголовком и выдавать события по одному.

    При skip=True неверная запись выдаётся как InvalidRecord, иначе возникает
    исключение. После восстанавливаемой ошибки синтаксиса чтение продолжается.
    """
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        try:
            fields = reader.fieldnames
            if fields is None:
                return
            if not FIELDS_SET.issubset(fields):
                raise InvalidEventError("CSV header misses required fields")
        except (csv.Error, InvalidEventError) as e:
            num = max(reader.reader.line_num, 1)
            if not skip:
                raise InvalidEventError(f"line {num}: {e}") from e
            yield InvalidRecord(num=num, reason=str(e))
            return

        while True:
            try:
                data = next(reader)
            except StopIteration:
                return
            except csv.Error as e:
                num = reader.reader.line_num
                if not skip:
                    raise InvalidEventError(f"line {num}: {e}") from e
                yield InvalidRecord(num=num, reason=str(e))
                continue

            num = reader.line_num
            try:
                if None in data:
                    raise InvalidEventError(f"line {num}: too many CSV values")
                validate(num, str(data), **data)
            except StreamStatsError as e:
                if not skip:
                    raise
                yield InvalidRecord(num=num, reason=str(e))
                continue
            yield Event(num, **{field: data[field] for field in FIELDS_LIST})


def parse_jsonl(path: str, skip: bool):
    """Разбирать по одному JSON-объекту на строку и выдавать события.

    При skip=True вместо неверной записи выдаёт InvalidRecord и продолжает
    чтение. При skip=False вызывает исключение с описанием ошибки.
    """
    with open(path, encoding="utf-8") as f:
        for num, line in enumerate(f, start=1):
            try:
                d = json.loads(line)
                if not isinstance(d, dict):
                    raise InvalidEventError("expected a JSON object")
            except (json.JSONDecodeError, InvalidEventError) as e:
                reason = e.msg if isinstance(e, json.JSONDecodeError) else str(e)
                message = f"line {num}: {reason}"
                if not skip:
                    raise InvalidEventError(message) from e
                yield InvalidRecord(num=num, reason=reason)
                continue
            try:
                validate(num, line, **d)
            except StreamStatsError as e:
                if not skip:
                    raise
                yield InvalidRecord(num=num, reason=str(e))
                continue
            yield Event(num, **{field: d[field] for field in FIELDS_LIST})


def get_parser(t: str, i: str, skip: bool):
    """Выбрать генератор для формата t, пути i и режима пропуска skip."""
    match t:
        case 'csv': return parse_csv(i, skip)
        case 'jsonl': return parse_jsonl(i, skip)
        case _: raise UnsupportedFormatError(f"Unsupported format: {t}")
