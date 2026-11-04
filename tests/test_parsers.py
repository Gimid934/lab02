"""Проверяем чтение файлов напрямую, без запуска CLI."""

import json

import pytest

from streamstats.errors import (
    InvalidEventError,
    InvalidLevelError,
    UnsupportedFormatError,
)
from streamstats.models import Event, InvalidRecord
from streamstats.parsers import get_parser, parse_csv, parse_jsonl


def test_jsonl_basic(tmp_path):
    """JSONL: поля события и Unicode сохраняются при чтении."""
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"timestamp":"2026-11-03T10:00:00+03:00",'
        '"level":"INFO","source":"app","message":"Привет 🐍"}\n',
        encoding="utf-8",
    )

    events = list(parse_jsonl(str(path), False))

    assert len(events) == 1
    assert isinstance(events[0], Event)
    assert events[0].num == 1
    assert events[0].level == "INFO"
    assert events[0].source == "app"
    assert events[0].message == "Привет 🐍"


def test_csv_basic(tmp_path):
    """CSV: заголовок, запятая внутри сообщения и пустое сообщение."""
    path = tmp_path / "events.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00+03:00,INFO,app,"Привет, мир"\n'
        '2026-11-03T10:01:00+03:00,ERROR,db,\n',
        encoding="utf-8",
    )

    events = list(parse_csv(str(path), False))

    assert len(events) == 2
    assert events[0].num == 2
    assert events[0].message == "Привет, мир"
    assert events[1].level == "ERROR"
    assert events[1].message == ""


def test_empty_files(tmp_path):
    """В пустом файле нет событий независимо от формата."""
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")

    assert list(parse_jsonl(str(path), False)) == []
    assert list(parse_csv(str(path), False)) == []


def test_jsonl_invalid_json(tmp_path):
    """Без пропуска повреждённый JSON должен вызвать исключение."""
    path = tmp_path / "broken.jsonl"
    path.write_text('{"timestamp":\n', encoding="utf-8")

    with pytest.raises(InvalidEventError):
        list(parse_jsonl(str(path), False))


def test_jsonl_skip_and_continue(tmp_path):
    """С пропуском парсер сообщает об ошибке и читает следующее событие."""
    path = tmp_path / "events.jsonl"
    path.write_text(
        'broken json\n'
        '{"timestamp":"2026-11-03T10:00:00+03:00",'
        '"level":"INFO","source":"app","message":"ok"}\n',
        encoding="utf-8",
    )

    events = list(parse_jsonl(str(path), True))

    assert len(events) == 2
    assert isinstance(events[0], InvalidRecord)
    assert events[0].num == 1
    assert events[0].reason != ""
    assert isinstance(events[1], Event)
    assert events[1].num == 2


def test_csv_invalid_level(tmp_path):
    """CSV без пропуска: неизвестный уровень вызывает исключение."""
    path = tmp_path / "broken.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00+03:00,HELLO,app,ok\n',
        encoding="utf-8",
    )

    with pytest.raises(InvalidLevelError):
        list(parse_csv(str(path), False))


def test_csv_skip_and_continue(tmp_path):
    """CSV с пропуском: плохая запись не мешает прочитать следующую."""
    path = tmp_path / "events.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00+03:00,HELLO,app,bad\n'
        '2026-11-03T10:01:00+03:00,ERROR,db,ok\n',
        encoding="utf-8",
    )

    events = list(parse_csv(str(path), True))

    assert len(events) == 2
    assert isinstance(events[0], InvalidRecord)
    assert events[0].num == 2
    assert isinstance(events[1], Event)
    assert events[1].num == 3
    assert events[1].source == "db"


def test_jsonl_missing_field(tmp_path):
    """Обязательное поле message отсутствует."""
    path = tmp_path / "missing.jsonl"
    data = {"timestamp": "2026-11-03T10:00:00+03:00",
            "level": "INFO", "source": "app"}
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(InvalidEventError):
        list(parse_jsonl(str(path), False))


def test_jsonl_not_object(tmp_path):
    """Список — корректный JSON, но не событие."""
    path = tmp_path / "array.jsonl"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(InvalidEventError):
        list(parse_jsonl(str(path), False))


def test_csv_missing_header(tmp_path):
    """В заголовке CSV должны присутствовать все обязательные поля."""
    path = tmp_path / "missing.csv"
    path.write_text("timestamp,level,source\n", encoding="utf-8")

    with pytest.raises(InvalidEventError):
        list(parse_csv(str(path), False))


def test_csv_unicode(tmp_path):
    """Проверка Unicode в источнике и сообщении."""
    path = tmp_path / "unicode.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00+03:00,INFO,приложение,Привет 🐍\n',
        encoding="utf-8",
    )

    events = list(parse_csv(str(path), False))

    assert len(events) == 1
    assert events[0].source == "приложение"
    assert events[0].message == "Привет 🐍"


def test_jsonl_timestamp_z(tmp_path):
    """Z обозначает UTC и должен приниматься в Python 3.10."""
    path = tmp_path / "utc.jsonl"
    path.write_text(
        '{"timestamp":"2026-11-03T10:00:00Z",'
        '"level":"INFO","source":"app","message":"ok"}\n',
        encoding="utf-8",
    )

    events = list(parse_jsonl(str(path), False))

    assert len(events) == 1
    assert isinstance(events[0], Event)
    assert events[0].timestamp == "2026-11-03T10:00:00Z"


def test_csv_syntax_error_skip_and_continue(tmp_path):
    """После лишнего символа за кавычкой следующая запись не теряется."""
    path = tmp_path / "broken.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00Z,INFO,app,"bad"x\n'
        '2026-11-03T10:01:00Z,ERROR,db,ok\n',
        encoding="utf-8",
    )

    events = list(parse_csv(str(path), True))

    assert len(events) == 2
    assert isinstance(events[0], InvalidRecord)
    assert events[0].num == 2
    assert isinstance(events[1], Event)
    assert events[1].num == 3
    assert events[1].source == "db"


def test_csv_syntax_error_without_skip(tmp_path):
    """Синтаксическая ошибка CSV сообщает правильную физическую строку."""
    path = tmp_path / "broken.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00Z,INFO,app,"bad"x\n',
        encoding="utf-8",
    )

    with pytest.raises(InvalidEventError, match="line 2:"):
        list(parse_csv(str(path), False))


def test_csv_multiline_after_syntax_error(tmp_path):
    """Восстановление не ломает корректное сообщение с переносом строки."""
    path = tmp_path / "multiline.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00Z,INFO,app,"bad"x\n'
        '2026-11-03T10:01:00Z,INFO,app,"Первая\nВторая"\n',
        encoding="utf-8",
        newline="",
    )

    events = list(parse_csv(str(path), True))

    assert len(events) == 2
    assert isinstance(events[0], InvalidRecord)
    assert events[1].num == 4
    assert events[1].message == "Первая\nВторая"


def test_csv_unclosed_quote_at_end(tmp_path):
    """Незакрытая кавычка в конце файла выдаёт один пропуск и завершает чтение."""
    path = tmp_path / "unclosed.csv"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00Z,INFO,app,"unfinished\n',
        encoding="utf-8",
    )

    events = list(parse_csv(str(path), True))

    assert len(events) == 1
    assert isinstance(events[0], InvalidRecord)
    assert events[0].num == 2


def test_unsupported_parser_format():
    """Неизвестный формат вызывает собственное исключение программы."""
    with pytest.raises(UnsupportedFormatError, match="xml"):
        get_parser("xml", "input.xml", False)
