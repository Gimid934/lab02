"""Потоковый анализ событий одного файла."""
import logging

from streamstats.errors import (
    InvalidEventError,
    InvalidTimestampError,
    StreamStatsError,
)
from streamstats.models import Event, InvalidRecord
from streamstats.parsers import parse_timestamp

logger = logging.getLogger(__name__)


def analyze(event_gen, file_num: int, skip: bool) -> dict:
    """Подсчитать статистику одного файла без накопления событий в списке.

    event_gen выдаёт Event или InvalidRecord.
    skip определяет, нужно ли пропускать неверные записи.

    Возвращает счётчики событий, уровней, источников, ошибок и границы времени.
    Топ источников вычисляется позже, при объединении файлов в CLI.
    """
    total = 0
    skipped = 0
    lvls = {}
    srcs = {}
    error_sources: dict[str, int] = {}
    datemin = None
    datemax = None
    event_gen = iter(event_gen)
    while True:
        try:
            event: Event = next(event_gen)
        except StopIteration:
            break
        except StreamStatsError as e:
            message = f"File num {file_num}: {e}"
            if not skip:
                raise type(e)(message) from e
            skipped += 1
            logger.warning("%s", message)
            continue

        if isinstance(event, InvalidRecord):
            message = f"File {file_num}, line {event.num}: {event.reason}"
            if not skip:
                raise InvalidEventError(message)
            skipped += 1
            logger.warning("%s", message)
            continue

        try:
            timestamp = parse_timestamp(event.timestamp)
            if datemin is None or datemax is None:
                datemin = datemax = timestamp
            else:
                datemin = min(timestamp, datemin)
                datemax = max(timestamp, datemax)
        except (ValueError, TypeError) as e:
            message = (f"File {file_num}, line {event.num}: invalid timestamp")
            if not skip:
                raise InvalidTimestampError(message) from e
            skipped += 1
            logger.warning("%s", message)
            continue

        total += 1

        if event.level not in lvls:
            lvls[event.level] = 1
        else:
            lvls[event.level] += 1

        if event.source not in srcs:
            srcs[event.source] = 1
        else:
            srcs[event.source] += 1

        if event.level in ("ERROR", "CRITICAL"):
            error_sources[event.source] = error_sources.get(event.source, 0) + 1
    return {
        "total_events": total,
        "skipped_lines": skipped,
        "by_level": lvls,
        "by_source": srcs,
        "error_sources": error_sources,
        "first_timestamp": datemin.isoformat() if datemin is not None else None,
        "last_timestamp": datemax.isoformat() if datemax is not None else None,
    }
