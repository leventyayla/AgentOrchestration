import sys

import pytest

from src.cli import main


class TestCliDeployDryRun:
    def test_deploy_dry_run_validates_manifest_and_skips_backend_mutation(
        self, tmp_path, monkeypatch, capsys
    ):
        manifest = tmp_path / "agent.yaml"
        manifest.write_text("name: test-agent\n", encoding="utf-8")
        backend_calls = []

        def fail_if_called(manifest_path):
            backend_calls.append(manifest_path)
            raise AssertionError("dry-run must not call the live deploy backend")

        monkeypatch.setattr(main, "deploy_agent", fail_if_called)
        monkeypatch.setattr(
            sys, "argv", ["ao", "deploy", str(manifest), "--dry-run"]
        )

        main.cli()

        captured = capsys.readouterr()
        assert "Dry run successful" in captured.out
        assert str(manifest) in captured.out
        assert backend_calls == []

    def test_deploy_dry_run_rejects_missing_manifest(
        self, tmp_path, monkeypatch, capsys
    ):
        missing_manifest = tmp_path / "missing.yaml"
        monkeypatch.setattr(
            sys, "argv", ["ao", "deploy", str(missing_manifest), "--dry-run"]
        )

        with pytest.raises(SystemExit) as excinfo:
            main.cli()

        captured = capsys.readouterr()
        assert excinfo.value.code == 2
        assert "Manifest file does not exist" in captured.err
        assert str(missing_manifest) in captured.err

    def test_deploy_without_dry_run_validates_then_uses_backend(
        self, tmp_path, monkeypatch
    ):
        manifest = tmp_path / "agent.yaml"
        manifest.write_text("name: test-agent\n", encoding="utf-8")
        backend_calls = []

        def record_deploy(manifest_path):
            backend_calls.append(manifest_path)

        monkeypatch.setattr(main, "deploy_agent", record_deploy)
        monkeypatch.setattr(sys, "argv", ["ao", "deploy", str(manifest)])

        main.cli()

        assert backend_calls == [str(manifest)]
