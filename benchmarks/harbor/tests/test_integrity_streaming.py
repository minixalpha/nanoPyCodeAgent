"""Large native JSON events retain exact text and normal process deadlines."""

import asyncio
import sys

import pytest

from harbor_adapter.integrity_environment import IntegrityDockerEnvironment


async def process(code, stdin=False):
    return await asyncio.create_subprocess_exec(
        sys.executable, "-c", code,
        stdin=asyncio.subprocess.PIPE if stdin else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )


def test_large_json_and_split_utf8_preserve_stdin_and_collected_output():
    async def run():
        child = await process("import sys; data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data)", stdin=True)
        original = ('{"text":"' + '€' * 100000 + '"}\n').encode() + b'\xff\xe2'
        output = []

        async def callback(text, stream):
            assert stream == "stdout"
            output.append(text)

        result = await IntegrityDockerEnvironment._collect_streamed_output(
            child, timeout_sec=5, stdin_data=original, on_output=callback,
        )
        assert result.return_code == 0
        assert result.stdout == "".join(output) == original.decode(errors="replace")
        assert len(output) > 1

    asyncio.run(run())


def test_stream_deadline_includes_exit_after_stdout_closes():
    async def run():
        child = await process("import os,time; os.close(1); os.close(2); time.sleep(60)")

        async def callback(*_):
            pass

        with pytest.raises(RuntimeError, match="timed out"):
            await IntegrityDockerEnvironment._collect_streamed_output(child, timeout_sec=.1, on_output=callback)
        assert child.returncode is not None

    asyncio.run(run())


@pytest.mark.parametrize("cancel", [False, True])
def test_callback_failure_or_cancellation_terminates_process(cancel):
    async def run():
        child = await process("import time; print('ready',flush=True); time.sleep(60)")
        ready = asyncio.Event()

        async def callback(*_):
            ready.set()
            if not cancel:
                raise ValueError("collector failed")

        task = asyncio.create_task(IntegrityDockerEnvironment._collect_streamed_output(
            child, timeout_sec=None, on_output=callback,
        ))
        await asyncio.wait_for(ready.wait(), 5)
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else ValueError):
            await task
        assert child.returncode is not None

    asyncio.run(run())
