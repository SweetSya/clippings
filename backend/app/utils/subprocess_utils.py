import asyncio
from typing import Tuple, List, Optional

async def run_with_timeout(
    cmd: List[str],
    timeout_seconds: float = 300.0,
    line_callback: Optional[callable] = None
) -> Tuple[int, str, str]:
    """
    Run subprocess asynchronously with a timeout.
    Optionally calls `line_callback(line)` for each line in stdout/stderr for progress tracking.
    Returns (return_code, stdout, stderr).
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout_lines = []
    stderr_lines = []

    async def read_stream(stream, lines_collector, is_stdout=True):
        while True:
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").strip()
            lines_collector.append(line)
            if line_callback:
                try:
                    res = line_callback(line)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass

    try:
        await asyncio.wait_for(
            asyncio.gather(
                read_stream(process.stdout, stdout_lines, True),
                read_stream(process.stderr, stderr_lines, False),
                process.wait()
            ),
            timeout=timeout_seconds
        )
        rc = process.returncode
    except asyncio.TimeoutError:
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        rc = -1
        stderr_lines.append(f"Command timed out after {timeout_seconds} seconds")

    return rc, "\n".join(stdout_lines), "\n".join(stderr_lines)
