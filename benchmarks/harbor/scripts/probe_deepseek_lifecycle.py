"""Probe sdk-minimal background-server lifetime with upstream keyless fixtures."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-source', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    source, runtime = args.upstream_source.resolve(), args.runtime.resolve()
    sys.path.insert(0, str(source / 'python/sdk/src'))
    from deepseek_harness import DeepSeekHarness
    fixture = source / 'scripts/smoke-python-runtime.py'
    spec = importlib.util.spec_from_file_location('upstream_smoke', fixture)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    calls = 0
    def completion(_body):
        nonlocal calls
        calls += 1
        if calls == 1:
            return smoke.tool_call_chunks('background-server', 'bash', {
                'command': f'nohup python3 -m http.server {port} --bind 127.0.0.1 > server.log 2>&1 & echo $! > server.pid; sleep 1',
            })
        return smoke.text_chunks('Lifecycle probe completed.')
    smoke.completion_chunks = completion
    def reachable():
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False
    with tempfile.TemporaryDirectory(prefix='dsh-lifecycle-') as temporary, smoke.MockModel() as model:
        cwd = Path(temporary)
        with DeepSeekHarness(provider='deepseek-official', model='smoke-model',
                profile='sdk-minimal', cwd=str(cwd), dsh_home=str(cwd / 'home'),
                dsh_bin=str(runtime), api_key='keyless-lifecycle-probe',
                base_url=model.url, request_timeout_seconds=60) as harness:
            result = harness.run('Start the probe server.', session_id='lifecycle')
            before_close = reachable()
        time.sleep(0.25)
        after_close = reachable()
        # The probe must not leave its explicitly created HTTP server behind.
        if after_close:
            import os
            import signal
            pid = int((cwd / 'server.pid').read_text())
            command = (Path('/proc') / str(pid) / 'cmdline').read_bytes()
            if b'http.server' in command and str(port).encode() in command:
                os.kill(pid, signal.SIGTERM)
        report = {
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'profile': 'sdk-minimal', 'finish_reason': result.finish_reason,
            'local_mock_requests': calls, 'real_model_calls': 0,
            'server_reachable_before_sdk_close': before_close,
            'server_reachable_after_sdk_close': after_close,
            'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'upstream_fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
            'runtime_sha256': hashlib.sha256(runtime.read_bytes()).hexdigest(),
        }
    print(json.dumps(report, indent=2))
    return 0 if result.finish_reason == 'completed' and before_close and calls == 2 else 1


if __name__ == '__main__':
    raise SystemExit(main())
