"""Optional real Docker probe; no model calls or benchmark solution access.

Set NANOPY_INTEGRITY_TEST_IMAGE to an existing Linux image containing python3
and CA certificates. The test creates and removes only its own containers.
"""

import asyncio
import json
import os
import shlex
import uuid

import pytest
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths

from harbor_adapter.integrity_environment import IntegrityDockerEnvironment


@pytest.mark.skipif(not os.environ.get("NANOPY_INTEGRITY_TEST_IMAGE"), reason="Explicit Docker probe image required")
def test_real_egress_rejects_reference_hosts_and_packet_mark_bypass(tmp_path):
    directory = tmp_path / "environment"
    directory.mkdir()
    paths = TrialPaths(trial_dir=tmp_path / "trial")
    paths.mkdir()
    environment = IntegrityDockerEnvironment(
        environment_dir=directory, environment_name="integrity-probe",
        session_id="integrity-probe-" + uuid.uuid4().hex,
        trial_paths=paths,
        task_env_config=EnvironmentConfig(docker_image=os.environ["NANOPY_INTEGRITY_TEST_IMAGE"]),
        integrity_policy={"allowed_hosts": ["api.deepseek.com"]},
    )

    async def exercise():
        try:
            await environment.start(force_build=False)
            try:
                await environment.integrity_preflight()
            except RuntimeError:
                print((await environment.exec(command="cat /etc/resolv.conf")).stdout)
                print((await environment._run_docker_compose_command([
                    "logs", "--no-color", environment._EGRESS_CONTROL_SERVICE_NAME,
                ])).stdout)
                raise
            async with environment.agent_phase():
                for url in ("https://raw.githubusercontent.com/", "https://github.com/", "https://example.com/"):
                    assert not (await environment._probe(url))["reachable"]
                code = '''import socket
s = socket.socket()
try:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_MARK, 114514)
except PermissionError:
    print("mark denied")
else:
    raise SystemExit("SO_MARK bypass remains available")
'''
                result = await environment.exec(command=shlex.join(["python3", "-I", "-c", code]))
                assert result.return_code == 0 and "mark denied" in result.stdout
                result = await environment.exec(command="test ! -e /logs/verifier")
                assert result.return_code == 0
            assert (environment.evidence_dir / "egress-log.json").exists()
            assert json.loads((environment.evidence_dir / "enforcement.json").read_text())["preflight"] == "passed"
            result = await environment.exec(
                command="mkdir -m 755 /logs/verifier && printf stale > /logs/verifier/reward.txt && printf stale > /logs/verifier/reward.json",
                user="root",
            )
            assert result.return_code == 0
            with environment.with_default_user("65534:65534"):
                await environment.prepare_verification()
                code = '''import os
from pathlib import Path
assert os.geteuid() == 65534
logs = Path('/logs/verifier')
assert not (logs / 'reward.txt').exists()
assert not (logs / 'reward.json').exists()
(logs / 'test-stdout.txt').write_text('verifier output')
(logs / 'reward.txt').write_text('1')
(logs / 'reward.json').write_text('{"reward": 1}')
archive = logs / 'attempts' / '1'
archive.mkdir(parents=True)
(archive / 'test-stdout.txt').write_text('archived output')
'''
                result = await environment.exec(command=shlex.join(["python3", "-I", "-c", code]))
                assert result.return_code == 0, result.stdout or result.stderr
        finally:
            # Do not remove any pre-existing image, including benchmark images.
            await environment.stop(delete=False)

    asyncio.run(exercise())


@pytest.mark.skipif(not os.environ.get("NANOPY_INTEGRITY_TEST_IMAGE"), reason="Explicit Docker probe image required")
def test_verified_cache_exists_only_before_and_after_model_phase(tmp_path):
    from pathlib import Path
    from harbor_adapter.dependency_cache import snapshot_scripts
    directory = tmp_path / "environment"
    directory.mkdir()
    paths = TrialPaths(trial_dir=tmp_path / "trial")
    paths.mkdir()
    settings = snapshot_scripts(Path(__file__).resolve().parents[3], tmp_path / "scripts", tmp_path / "cache")
    environment = IntegrityDockerEnvironment(
        environment_dir=directory, environment_name="cache-probe",
        session_id="cache-probe-" + uuid.uuid4().hex, trial_paths=paths,
        task_env_config=EnvironmentConfig(docker_image=os.environ["NANOPY_INTEGRITY_TEST_IMAGE"]),
        integrity_policy={"allowed_hosts": ["api.deepseek.com"]}, dependency_cache=settings,
    )
    fetch = '''import hashlib, json, urllib.request
base = 'http://127.0.0.1:18744'
with urllib.request.urlopen(base + '/simple/pytest/', timeout=30) as response:
    index = json.load(response)
file = next(f for f in index['files'] if f['filename'] == 'pytest-8.4.1-py3-none-any.whl')
with urllib.request.urlopen(base + file['url'], timeout=60) as response:
    data = response.read()
assert hashlib.sha256(data).hexdigest() == file['hashes']['sha256']
assert len(data) == file['size']
print('original wheel verified')
'''

    async def exercise():
        try:
            await environment.start(force_build=False)
            async with environment.dependency_cache.phase("setup"):
                result = await environment.exec(command=shlex.join(["python3", "-I", "-c", fetch]))
                assert result.return_code == 0, result.stdout or result.stderr
            await environment.integrity_preflight()
            async with environment.agent_phase():
                await environment.dependency_cache.assert_stopped()
                assert not (await environment._probe("https://raw.githubusercontent.com/"))["reachable"]
                with pytest.raises(RuntimeError, match="model work"):
                    async with environment.dependency_cache.phase("verifier"):
                        pytest.fail("Cache reopened during model work")
            await environment.prepare_verification()
            async with environment.dependency_cache.phase("verifier"):
                result = await environment.exec(command=shlex.join(["python3", "-I", "-c", fetch]))
                assert result.return_code == 0, result.stdout or result.stderr
            await environment.dependency_cache.assert_stopped()
            proof = json.loads((environment.evidence_dir / "enforcement.json").read_text())
            assert proof["dependency_cache"]["absent_before_agent"] is True
            log = json.loads((environment.evidence_dir / "dependency-cache-verifier-log.json").read_text())["log"]
            assert '"cache_hit": true' in log
        finally:
            await environment.stop(delete=False)

    asyncio.run(exercise())
