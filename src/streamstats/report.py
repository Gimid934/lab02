"""Формирование отчёта."""
import json
from pathlib import Path

from streamstats.errors import CLIConfigError


def validate_output(inputs: list[str], output: str | None) -> None:
    """Запретить запись отчёта в любой входной файл."""
    output_path = Path(output or "REPORT.json")
    for num, source in enumerate(inputs, start=1):
        input_path = Path(source)
        same_path = output_path.resolve() == input_path.resolve()
        same_file = (
            output_path.exists() and input_path.exists()
            and output_path.samefile(input_path)
        )
        if same_path or same_file:
            raise CLIConfigError(
                f"File num {num}: output must differ from input ({source})"
            )


def write_report(output: str | None, report: dict) -> None:
    """Записать словарь report в JSON-файл output с кодировкой UTF-8.

    Если output не задан, используется REPORT.json в текущей папке.
    Существующий файл перезаписывается.
    """
    output = output or "REPORT.json"
    with open(output, "w", encoding="utf-8") as f:
        f.write(json.dumps(report))
