import json
import subprocess
import sys

from src.agent.runtime import AgentRuntime, RuntimeState


def test_stop_persists_terminal_state_and_cleans_temp_dir(tmp_path):
    runtime = AgentRuntime(runtime_path=str(tmp_path))

    assert runtime.start("agent-1", [sys.executable, "-c", "import time; time.sleep(30)"])
    temp_dir = runtime.temp_dir("agent-1")
    (temp_dir / "scratch.txt").write_text("temporary work", encoding="utf-8")

    assert temp_dir.exists()
    assert runtime.stop("agent-1", timeout=1)

    state = json.loads(runtime.state_file("agent-1").read_text(encoding="utf-8"))
    assert state["state"] == RuntimeState.STOPPED.value
    assert state["terminal"] is True
    assert not temp_dir.exists()


def test_crashed_process_is_recorded_once_and_temp_cleanup_is_idempotent(tmp_path):
    runtime = AgentRuntime(runtime_path=str(tmp_path))

    assert runtime.start("agent-2", [sys.executable, "-c", "raise SystemExit(7)"])
    proc = runtime._processes["agent-2"]
    proc.wait(timeout=5)
    temp_dir = runtime.temp_dir("agent-2")
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "orphan.tmp").write_text("stale", encoding="utf-8")

    assert runtime.get_state("agent-2") == RuntimeState.CRASHED
    first_state = json.loads(runtime.state_file("agent-2").read_text(encoding="utf-8"))
    assert first_state["state"] == RuntimeState.CRASHED.value
    assert first_state["returncode"] == 7
    assert not temp_dir.exists()

    assert runtime.get_state("agent-2") == RuntimeState.CRASHED
    assert not temp_dir.exists()


def test_start_failure_persists_crash_before_cleanup(tmp_path, monkeypatch):
    runtime = AgentRuntime(runtime_path=str(tmp_path))

    def fail_to_spawn(*args, **kwargs):
        raise OSError("spawn failed")

    monkeypatch.setattr(subprocess, "Popen", fail_to_spawn)

    assert runtime.start("agent-3", ["missing-binary"]) is False

    state = json.loads(runtime.state_file("agent-3").read_text(encoding="utf-8"))
    assert state["state"] == RuntimeState.CRASHED.value
    assert state["terminal"] is True
    assert "spawn failed" in state["error"]
    assert not runtime.temp_dir("agent-3").exists()
