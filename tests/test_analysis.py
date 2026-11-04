import pytest

from streamstats.analysis import analyze
from streamstats.errors import InvalidEventError, InvalidLevelError
from streamstats.models import Event, InvalidRecord


def test_counts():
    """Проверить счётчики уровней, источников и ERROR/CRITICAL."""
    events = [
        Event(1, "2026-11-03T10:00:00+03:00", "INFO", "app", "ok"),
        Event(2, "2026-11-03T10:01:00+03:00", "ERROR", "db", "bad"),
        Event(3, "2026-11-03T10:02:00+03:00", "CRITICAL", "db", "bad"),
        Event(4, "2026-11-03T10:03:00+03:00", "WARNING", "app", "warn"),
    ]

    report = analyze(iter(events), 1, False)

    assert report["total_events"] == 4
    assert report["skipped_lines"] == 0
    assert report["by_level"] == {"INFO": 1, "ERROR": 1, "CRITICAL": 1, "WARNING": 1}
    assert report["by_source"] == {"app": 2, "db": 2}
    assert report["error_sources"] == {"db": 2}


def test_empty_report():
    """Для пустого потока вернуть нулевые счётчики и пустые границы времени."""
    report = analyze(iter([]), 1, False)

    assert report["total_events"] == 0
    assert report["skipped_lines"] == 0
    assert report["by_level"] == {}
    assert report["by_source"] == {}
    assert report["error_sources"] == {}
    assert report["first_timestamp"] is None
    assert report["last_timestamp"] is None


def test_first_record_invalid():
    """Пропустить первую запись и взять время из первого корректного события."""
    events = [
        InvalidRecord(1, "Invalid JSON"),
        Event(2, "2026-11-03T10:00:00+03:00", "INFO", "app", "ok"),
    ]

    report = analyze(iter(events), 2, True)

    assert report["total_events"] == 1
    assert report["skipped_lines"] == 1
    assert report["first_timestamp"] == "2026-11-03T10:00:00+03:00"
    assert report["last_timestamp"] == report["first_timestamp"]


def test_time_order_and_timezones():
    """Выбрать границы времени с учётом часовых смещений и порядка записей."""
    events = [
        Event(1, "2026-11-03T12:00:00+03:00", "INFO", "app", "09:00 UTC"),
        Event(2, "2026-11-03T10:00:00+00:00", "INFO", "app", "10:00 UTC"),
        Event(3, "2026-11-03T08:00:00+00:00", "INFO", "app", "08:00 UTC"),
    ]

    report = analyze(iter(events), 1, False)

    assert report["first_timestamp"] == "2026-11-03T08:00:00+00:00"
    assert report["last_timestamp"] == "2026-11-03T10:00:00+00:00"


def test_invalid_record_without_skip():
    """Остановиться на InvalidRecord, если пропуск ошибок отключён."""
    events = [InvalidRecord(3, "Invalid event")]

    with pytest.raises(InvalidEventError, match="File 2"):
        analyze(iter(events), 2, False)


def test_parser_error_keeps_its_type():
    """Сохранить класс ошибки парсера и добавить номер входного файла."""
    def broken_parser():
        """Выдать одно событие, затем вызвать ошибку уровня."""
        yield Event(1, "2026-11-03T10:00:00+03:00", "INFO", "app", "ok")
        raise InvalidLevelError("line 2: incorrect level")

    with pytest.raises(InvalidLevelError, match="File num 3"):
        analyze(broken_parser(), 3, False)
