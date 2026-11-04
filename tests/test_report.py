import pytest

from streamstats.errors import CLIConfigError
from streamstats.report import validate_output


def test_output_matches_second_input(tmp_path):
    """Проверка совпадения выхода со вторым входным файлом."""
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    with pytest.raises(CLIConfigError, match="File num 2"):
        validate_output([str(first), str(second)], str(second))

    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"


def test_output_is_hard_link_to_input(tmp_path):
    """Два разных имени одного файла тоже нельзя использовать как вход и выход."""
    source = tmp_path / "events.jsonl"
    output = tmp_path / "report.json"
    source.write_text("original", encoding="utf-8")
    output.hardlink_to(source)

    with pytest.raises(CLIConfigError):
        validate_output([str(source)], str(output))

    assert source.read_text(encoding="utf-8") == "original"
