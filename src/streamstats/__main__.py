"""Запуск подкоманды analyze."""
import logging
from datetime import datetime
from typing import Annotated, Literal

import typer

from streamstats.analysis import analyze
from streamstats.errors import InvalidTimestampError, StreamStatsError
from streamstats.parsers import get_parser
from streamstats.report import validate_output, write_report

logging.basicConfig(
    filename="logs.log",
    encoding="utf-8",
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = typer.Typer(add_completion=False)


@app.callback()
def main() -> None:
    """Потоковый анализатор событий из CSV и JSONL."""


@app.command("analyze")
def analyze_command(
    inputs: Annotated[
        list[str], typer.Argument(metavar="INPUT", help="Один или несколько входных файлов."),
    ],
    file_format: Annotated[
        Literal["csv", "jsonl"],
        typer.Option("--format", help="Формат всех входных файлов: csv или jsonl."),
    ],
    output: Annotated[
        str | None,
        typer.Option("--output", metavar="REPORT file",
                     help="Файл JSON-отчёта. По умолчанию REPORT.json."),
    ] = None,
    skip_invalid: Annotated[
        bool, typer.Option("--skip-invalid", help="Пропускать неверные записи с WARNING в логе."),
    ] = False,
) -> None:
    """Прочитать события, объединить статистику файлов и записать JSON-отчёт.

    По умолчанию ошибка события останавливает обработку с кодом 2.
    Опция --skip-invalid включает пропуск неверных записей.
    """
    merged_report: dict = {
        "total_events": 0,
        "skipped_lines": 0,
        "by_level": {},
        "by_source": {},
        "error_sources": {},
        "first_timestamp": None,
        "last_timestamp": None,
    }
    try:
        validate_output(inputs, output)
        for num, inp in enumerate(inputs, start=1):
            event_gen = get_parser(file_format, inp, skip_invalid)
            report = analyze(event_gen, num, skip_invalid)

            merged_report["total_events"] += report["total_events"]
            merged_report["skipped_lines"] += report["skipped_lines"]

            for key in ("by_level", "by_source", "error_sources"):
                for name, count in report[key].items():
                    if name not in merged_report[key]:
                        merged_report[key][name] = count
                    else:
                        merged_report[key][name] += count

            for key, min_max in (("first_timestamp", min), ("last_timestamp", max)):
                incoming = report[key]
                if incoming is None:
                    continue
                current = merged_report[key]
                if current is None:
                    merged_report[key] = incoming
                    continue
                try:
                    merged_report[key] = min_max(
                        current, incoming, key=datetime.fromisoformat,
                    )
                except TypeError as exc:
                    raise InvalidTimestampError(
                        f"File {num}: cannot merge timestamps") from exc
    except StreamStatsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    error_sources = merged_report.pop("error_sources")
    ranked_sources = sorted(
        error_sources.items(), key=lambda item: (-item[1], item[0]),
    )
    merged_report["top_error_sources"] = [
        {"source": source, "count": count}
        for source, count in ranked_sources[:5]
    ]

    write_report(output, merged_report)


if __name__ == "__main__":
    app()
