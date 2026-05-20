import sys

import pytest

from src.cli.main import cli


def run_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["ao", *args])
    cli()


def test_status_writes_data_to_stdout_only(monkeypatch, capsys):
    run_cli(monkeypatch, "status")

    captured = capsys.readouterr()
    assert captured.out == "Checking agent status...\n"
    assert captured.err == ""


def test_missing_command_writes_validation_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ao"])

    with pytest.raises(SystemExit) as exc_info:
        cli()

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.out == ""
    assert "error: command is required" in captured.err
    assert "Available commands" in captured.err


def test_invalid_command_writes_argparse_error_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ao", "unknown"])

    with pytest.raises(SystemExit) as exc_info:
        cli()

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert captured.out == ""
    assert "invalid choice: 'unknown'" in captured.err
