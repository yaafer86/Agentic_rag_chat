"""Microsandbox — ephemeral Docker container for isolated Python execution.

Security envelope:
- cap_drop=["ALL"], security_opt=["no-new-privileges:true"]
- network_mode="none" (the spec forbids sandbox network access)
- read_only filesystem with tmpfs for /tmp and /sandbox
- mem_limit + cpu_quota from settings
- Timeout enforced via `container.wait(timeout=...)` + forced stop/remove
- Artifacts are collected from /sandbox/out before teardown

If the local Docker daemon is unreachable (no Docker in the test env), the executor
raises a clear `SandboxUnavailable` so the API returns 503 instead of hanging.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SandboxUnavailable(RuntimeError):  # noqa: N818 kept for API clarity
    """Raised when the Docker daemon is unreachable."""


@dataclass
class SandboxArtifact:
    name: str
    mime: str
    data: bytes


@dataclass
class SandboxResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    duration_ms: int = 0
    plots: list[bytes] = field(default_factory=list)
    artifacts: list[SandboxArtifact] = field(default_factory=list)


_BOOTSTRAP = r"""
import os, sys, io, base64, traceback, pathlib, mimetypes

pathlib.Path('/sandbox/out').mkdir(parents=True, exist_ok=True)
pathlib.Path('/sandbox/out/plots').mkdir(parents=True, exist_ok=True)
pathlib.Path('/sandbox/out/artifacts').mkdir(parents=True, exist_ok=True)

# Redirect matplotlib to a file-based backend.
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    _orig_show = plt.show
    _plot_idx = [0]
    def _show(*args, **kwargs):
        _plot_idx[0] += 1
        plt.savefig(f'/sandbox/out/plots/plot_{_plot_idx[0]:03d}.png', bbox_inches='tight')
        plt.close('all')
    plt.show = _show
except Exception:
    pass

os.chdir('/sandbox')

try:
    with open('/sandbox/user_code.py', 'r', encoding='utf-8') as f:
        code = f.read()
    exec(compile(code, '<user-code>', 'exec'), {'__name__': '__main__'})
except SystemExit:
    raise
except BaseException:
    traceback.print_exc()
    sys.exit(1)
"""


def _build_input_tar(code: str, files: list[dict[str, str]]) -> BytesIO:
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        _add_file(tar, "user_code.py", code.encode("utf-8"))
        _add_file(tar, "bootstrap.py", _BOOTSTRAP.encode("utf-8"))
        for f in files:
            name = f.get("name")
            data = f.get("base64")
            if not name or data is None:
                continue
            raw = base64.b64decode(data)
            _add_file(tar, f"inputs/{name}", raw)
    buf.seek(0)
    return buf


def _add_file(tar: tarfile.TarFile, arcname: str, data: bytes) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mtime = int(time.time())
    info.mode = 0o644
    tar.addfile(info, BytesIO(data))


def _extract_output(tar_bytes: bytes) -> tuple[list[bytes], list[SandboxArtifact]]:
    plots: list[bytes] = []
    artifacts: list[SandboxArtifact] = []
    with tarfile.open(fileobj=BytesIO(tar_bytes), mode="r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            path = member.name.lstrip("./")
            f = tar.extractfile(member)
            if not f:
                continue
            data = f.read()
            if path.startswith("out/plots/"):
                plots.append(data)
            elif path.startswith("out/artifacts/"):
                import mimetypes as _mt

                name = path.rsplit("/", 1)[-1]
                mime, _ = _mt.guess_type(name)
                artifacts.append(
                    SandboxArtifact(name=name, mime=mime or "application/octet-stream", data=data)
                )
    return plots, artifacts


def _run_sync(
    code: str,
    files: list[dict[str, str]],
    timeout_s: int,
    memory_mb: int,
) -> SandboxResult:
    try:
        import docker  # type: ignore[import-untyped]
        from docker.errors import DockerException  # type: ignore[import-untyped]
    except ImportError as e:  # pragma: no cover
        raise SandboxUnavailable("docker SDK not installed") from e

    s = get_settings()
    try:
        client = docker.from_env()
        client.ping()
    except DockerException as e:
        raise SandboxUnavailable(f"docker daemon unreachable: {e}") from e

    name = f"sandbox-{uuid.uuid4().hex[:12]}"
    container = client.containers.create(
        image=s.sandbox_image,
        name=name,
        command=["python", "-u", "/sandbox/bootstrap.py"],
        working_dir="/sandbox",
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        network_mode="none" if not s.sandbox_network_enabled else "bridge",
        mem_limit=f"{memory_mb}m",
        nano_cpus=1_000_000_000,  # 1 CPU
        read_only=True,
        tmpfs={"/sandbox": "rw,exec,size=128m", "/tmp": "rw,exec,size=64m"},  # noqa: S108 in-container tmpfs, not a host path
        detach=True,
        stdin_open=False,
        tty=False,
        environment={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
    )

    result = SandboxResult()
    start = time.monotonic()
    try:
        input_tar = _build_input_tar(code, files)
        container.put_archive("/sandbox", input_tar.getvalue())
        container.start()
        try:
            exit_info = container.wait(timeout=timeout_s)
            result.exit_code = int(exit_info.get("StatusCode", 1))
        except Exception:
            result.timed_out = True
            with contextlib.suppress(Exception):
                container.stop(timeout=1)
        result.stdout = container.logs(stdout=True, stderr=False).decode("utf-8", "replace")
        result.stderr = container.logs(stdout=False, stderr=True).decode("utf-8", "replace")
        if not result.timed_out:
            bits, _stat = container.get_archive("/sandbox/out")
            tar_bytes = b"".join(bits)
            result.plots, result.artifacts = _extract_output(tar_bytes)
    finally:
        try:
            container.remove(force=True)
        except Exception:
            logger.warning("failed to remove sandbox container %s", name, exc_info=True)
        result.duration_ms = int((time.monotonic() - start) * 1000)

    return result


async def run(
    code: str,
    *,
    files: list[dict[str, str]] | None = None,
    timeout_s: int | None = None,
    memory_mb: int | None = None,
) -> SandboxResult:
    s = get_settings()
    return await asyncio.to_thread(
        _run_sync,
        code,
        files or [],
        timeout_s or s.sandbox_timeout,
        memory_mb or s.sandbox_max_memory_mb,
    )


__all__ = ["SandboxArtifact", "SandboxResult", "SandboxUnavailable", "run"]


def _probe_result_shape(_obj: Any) -> Any:  # pragma: no cover - silence mypy unused
    return _obj
