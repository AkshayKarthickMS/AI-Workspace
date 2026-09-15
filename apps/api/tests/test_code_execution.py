"""Sandboxed code-execution tool tests, using a mocked Docker client -- no
live daemon required (AGENTS.md). These validate the security-critical
container configuration (network isolation, resource limits, non-root user)
and cleanup behavior, not real container execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.schemas.code_execution import CodeExecutionInput
from app.tools.code_execution import CodeExecutionTool


def _mock_container(
    *, exit_status: int = 0, stdout_text: str = "", stderr_text: str = ""
) -> MagicMock:
    container = MagicMock()
    container.wait.return_value = {"StatusCode": exit_status}

    def logs_side_effect(stdout: bool = True, stderr: bool = True) -> bytes:
        if stdout and not stderr:
            return stdout_text.encode("utf-8")
        if stderr and not stdout:
            return stderr_text.encode("utf-8")
        return (stdout_text + stderr_text).encode("utf-8")

    container.logs.side_effect = logs_side_effect
    return container


def test_execute_configures_network_disabled_and_resource_limits() -> None:
    client = MagicMock()
    container = _mock_container(stdout_text="hello\n")
    client.containers.run.return_value = container

    tool = CodeExecutionTool(
        timeout_seconds=5, memory_limit_mb=256, cpu_limit=0.5, docker_client=client
    )
    result = tool.execute(CodeExecutionInput(code="print('hello')"))

    assert result.exit_status == 0
    assert result.stdout.strip() == "hello"
    assert not result.timed_out

    _, kwargs = client.containers.run.call_args
    assert kwargs["network_disabled"] is True
    assert kwargs["mem_limit"] == "256m"
    assert kwargs["nano_cpus"] == 500_000_000
    assert kwargs["user"] == "nobody"
    container.remove.assert_called_once_with(force=True)


def test_execute_kills_container_on_timeout() -> None:
    client = MagicMock()
    container = _mock_container()
    container.wait.side_effect = TimeoutError("timed out")
    client.containers.run.return_value = container

    tool = CodeExecutionTool(docker_client=client)
    result = tool.execute(CodeExecutionInput(code="while True: pass"))

    assert result.timed_out is True
    assert result.exit_status == -1
    container.kill.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_execute_redacts_secrets_in_captured_output() -> None:
    client = MagicMock()
    container = _mock_container(stdout_text="api_key=sk-super-secret-value\n")
    client.containers.run.return_value = container

    tool = CodeExecutionTool(docker_client=client)
    result = tool.execute(CodeExecutionInput(code="print('leaked')"))

    assert "sk-super-secret-value" not in result.stdout
    assert "[REDACTED]" in result.stdout


def test_execute_cleans_up_scratch_directory() -> None:
    client = MagicMock()
    container = _mock_container()
    client.containers.run.return_value = container

    captured_dirs: list[Path] = []
    real_run_container = CodeExecutionTool._run_container

    def spy_run_container(self: CodeExecutionTool, scratch_dir: Path) -> object:
        captured_dirs.append(scratch_dir)
        assert scratch_dir.exists()
        assert (scratch_dir / "main.py").exists()
        return real_run_container(self, scratch_dir)

    tool = CodeExecutionTool(docker_client=client)
    with patch.object(CodeExecutionTool, "_run_container", spy_run_container):
        tool.execute(CodeExecutionInput(code="print(1)"))

    assert captured_dirs and not captured_dirs[0].exists()
