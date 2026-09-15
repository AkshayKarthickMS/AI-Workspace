"""Sandboxed Python code execution for the Analyst agent (ARCHITECTURE.md
section 10, section 12).

Every execution runs in an ephemeral, network-disabled, non-root, resource-
and time-bounded Docker container with no host filesystem access beyond a
disposable per-execution scratch directory mounted read-only. Generated code
is always treated as untrusted data — it is never ``eval``'d or ``exec``'d in
this process (AGENTS.md); this is the only place it ever runs.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from app.core.redaction import redact
from app.schemas.code_execution import CodeExecutionInput, CodeExecutionResult

_MAX_CAPTURED_OUTPUT = 20000


class SandboxExecutionError(RuntimeError):
    """Raised when the sandbox container itself could not be started."""


class CodeExecutionTool:
    def __init__(
        self,
        *,
        image: str = "python:3.12-slim",
        timeout_seconds: int = 30,
        memory_limit_mb: int = 512,
        cpu_limit: float = 1.0,
        docker_client: Any | None = None,
    ) -> None:
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        # Typed loosely on purpose: this is either a real docker.DockerClient
        # (lazily constructed below, never at import time) or a test double
        # that only needs to duck-type `.containers.run(...)`.
        self._client: Any = docker_client

    def _get_client(self) -> Any:
        if self._client is None:
            # Imported lazily so importing this module never requires the
            # `docker` package to reach a live daemon unless this is called.
            import docker

            self._client = docker.from_env()
        return self._client

    def execute(self, request: CodeExecutionInput) -> CodeExecutionResult:
        scratch_dir = Path(tempfile.mkdtemp(prefix="aegis-sandbox-"))
        try:
            (scratch_dir / "main.py").write_text(request.code, encoding="utf-8")
            return self._run_container(scratch_dir)
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def _run_container(self, scratch_dir: Path) -> CodeExecutionResult:
        client = self._get_client()
        start = time.monotonic()
        try:
            container = client.containers.run(
                self.image,
                ["python", "/workspace/main.py"],
                volumes={str(scratch_dir): {"bind": "/workspace", "mode": "ro"}},
                working_dir="/workspace",
                network_disabled=True,
                mem_limit=f"{self.memory_limit_mb}m",
                nano_cpus=int(self.cpu_limit * 1_000_000_000),
                user="nobody",
                detach=True,
                stdout=True,
                stderr=True,
            )
        except Exception as exc:
            raise SandboxExecutionError("Sandbox container could not be started") from exc

        timed_out = False
        try:
            wait_result = container.wait(timeout=self.timeout_seconds)
            exit_status = int(wait_result.get("StatusCode", -1))
        except Exception:
            timed_out = True
            exit_status = -1
            container.kill()
        finally:
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            container.remove(force=True)

        duration_ms = int((time.monotonic() - start) * 1000)
        return CodeExecutionResult(
            exit_status=exit_status,
            stdout=redact(stdout)[:_MAX_CAPTURED_OUTPUT],
            stderr=redact(stderr)[:_MAX_CAPTURED_OUTPUT],
            duration_ms=duration_ms,
            timed_out=timed_out,
        )
