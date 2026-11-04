"""Запускаем CLI и проверяем код завершения и созданный JSON-отчёт."""

import json

from typer.testing import CliRunner

from streamstats.__main__ import app


def test_cli_help():
    """Показать справку CLI с командой analyze."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "analyze" in result.output


def test_cli_two_files(tmp_path, monkeypatch):
    """Статистика двух файлов должна попасть в один отчёт."""
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    output = tmp_path / "report.json"
    first.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00+03:00,INFO,app,ok\n'
        '2026-11-03T10:01:00+03:00,ERROR,db,bad\n',
        encoding="utf-8",
    )
    second.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:02:00+03:00,CRITICAL,db,bad\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [
        "analyze", str(first), str(second), "--format", "csv", "--output", str(output),
    ])

    assert result.exit_code == 0, result.exception
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_events"] == 3
    assert report["by_source"] == {"app": 1, "db": 2}
    assert report["by_level"] == {"INFO": 1, "ERROR": 1, "CRITICAL": 1}
    assert report["first_timestamp"] == "2026-11-03T10:00:00+03:00"
    assert report["last_timestamp"] == "2026-11-03T10:02:00+03:00"
    assert report["top_error_sources"] == [{"source": "db", "count": 2}]


def test_cli_skip_invalid(tmp_path):
    """JSONL с ошибкой: --skip-invalid позволяет получить отчёт."""
    path = tmp_path / "events.jsonl"
    output = tmp_path / "report.json"
    path.write_text(
        'broken\n'
        '{"timestamp":"2026-11-03T10:00:00+03:00",'
        '"level":"INFO","source":"app","message":"ok"}\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(path), "--format", "jsonl", "--skip-invalid",
        "--output", str(output),
    ])

    assert result.exit_code == 0, result.exception
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_events"] == 1
    assert report["skipped_lines"] == 1
    assert report["top_error_sources"] == []


def test_cli_top_five(tmp_path):
    """Вывести пять источников с наибольшим числом ERROR/CRITICAL."""
    path = tmp_path / "events.csv"
    output = tmp_path / "report.json"
    text = "timestamp,level,source,message\n"
    for source, count in [("a", 6), ("b", 5), ("c", 4), ("d", 3), ("e", 2), ("f", 1)]:
        for _ in range(count):
            text += f"2026-11-03T10:00:00+03:00,ERROR,{source},bad\n"
    for _ in range(10):
        text += "2026-11-03T10:00:00+03:00,WARNING,noisy,warn\n"
    path.write_text(text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(path), "--format", "csv", "--output", str(output),
    ])

    assert result.exit_code == 0, result.exception
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["top_error_sources"] == [
        {"source": "a", "count": 6},
        {"source": "b", "count": 5},
        {"source": "c", "count": 4},
        {"source": "d", "count": 3},
        {"source": "e", "count": 2},
    ]


def test_cli_wrong_format():
    """Завершиться с кодом 2 при неизвестном значении --format."""
    runner = CliRunner()
    result = runner.invoke(app, ["analyze", "input.txt", "--format", "xml"])

    assert result.exit_code == 2


def test_cli_csv_skip_invalid(tmp_path, caplog):
    """CSV с ошибкой: пропуск учтён в отчёте, предупреждение записано в лог."""
    path = tmp_path / "events.csv"
    output = tmp_path / "report.json"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00+03:00,HELLO,app,bad\n'
        '2026-11-03T10:01:00+03:00,INFO,app,ok\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(path), "--format", "csv", "--skip-invalid",
        "--output", str(output),
    ])

    assert result.exit_code == 0, result.exception
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_events"] == 1
    assert report["skipped_lines"] == 1
    assert report["by_level"] == {"INFO": 1}

    assert "WARNING" in caplog.text
    assert "HELLO" in caplog.text


def test_cli_csv_error_without_skip(tmp_path):
    """CLI должен сообщить файл и строку и завершиться с кодом 2."""
    path = tmp_path / "broken.csv"
    output = tmp_path / "report.json"
    path.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00+03:00,HELLO,app,bad\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(path), "--format", "csv", "--output", str(output),
    ])

    assert result.exit_code == 2
    assert "File num 1" in result.output
    assert "2 Incorrect level" in result.output
    assert not output.exists()


def test_cli_jsonl_error_without_skip(tmp_path):
    """Повреждённый JSON должен приводить к коду CLI 2."""
    path = tmp_path / "broken.jsonl"
    output = tmp_path / "report.json"
    path.write_text('broken json\n', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(path), "--format", "jsonl", "--output", str(output),
    ])

    assert result.exit_code == 2
    assert "File num 1" in result.output
    assert "line 1" in result.output
    assert not output.exists()


def test_cli_merge_timestamps_z(tmp_path):
    """Z и +03:00 правильно сравниваются при анализе и слиянии файлов."""
    first = tmp_path / "utc.csv"
    second = tmp_path / "offset.csv"
    output = tmp_path / "report.json"
    first.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T10:00:00Z,INFO,app,ok\n'
        '2026-11-03T11:00:00Z,INFO,app,ok\n',
        encoding="utf-8",
    )
    second.write_text(
        'timestamp,level,source,message\n'
        '2026-11-03T12:00:00+03:00,INFO,app,ok\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(first), str(second), "--format", "csv", "--output", str(output),
    ])

    assert result.exit_code == 0, result.exception
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_events"] == 3
    assert report["skipped_lines"] == 0
    assert report["first_timestamp"] == "2026-11-03T12:00:00+03:00"
    assert report["last_timestamp"] == "2026-11-03T11:00:00+00:00"


def test_cli_output_matches_input(tmp_path):
    """Отклонить совпадающие пути и сохранить исходный файл без изменений."""
    path = tmp_path / "events.jsonl"
    content = (
        '{"timestamp":"2026-11-03T10:00:00Z",'
        '"level":"INFO","source":"app","message":"ok"}\n'
    )
    path.write_text(content, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(path), "--format", "jsonl", "--output", str(path),
    ])

    assert result.exit_code == 2
    assert "output must differ from input" in result.output
    assert path.read_text(encoding="utf-8") == content


def test_cli_default_output_matches_input(tmp_path, monkeypatch):
    """Защита работает и для имени REPORT.json, выбранного по умолчанию."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "REPORT.json"
    content = (
        '{"timestamp":"2026-11-03T10:00:00Z",'
        '"level":"INFO","source":"app","message":"ok"}\n'
    )
    path.write_text(content, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["analyze", str(path), "--format", "jsonl"])

    assert result.exit_code == 2
    assert "output must differ from input" in result.output
    assert path.read_text(encoding="utf-8") == content


def test_cli_jsonl_warning_line_seven(tmp_path, caplog):
    """В WARNING должен быть номер строки файла, а не строки JSON-декодера."""
    path = tmp_path / "events.jsonl"
    output = tmp_path / "report.json"
    valid_line = (
        '{"timestamp":"2026-11-03T10:00:00Z",'
        '"level":"INFO","source":"app","message":"ok"}\n'
    )
    path.write_text(valid_line * 6 + "broken\n" + valid_line, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, [
        "analyze", str(path), "--format", "jsonl", "--skip-invalid",
        "--output", str(output),
    ])

    assert result.exit_code == 0, result.exception
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_events"] == 7
    assert report["skipped_lines"] == 1
    assert "WARNING" in caplog.text
    assert "File 1, line 7:" in caplog.text
