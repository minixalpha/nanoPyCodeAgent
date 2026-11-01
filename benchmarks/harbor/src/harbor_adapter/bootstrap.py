"""Verified, reusable APT downloads and versioned verifier dependency profiles."""

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile


def default_cache_dir() -> Path:
    return Path(
        os.environ.get("NANOPY_HARBOR_CACHE", ".cache/nanopy-harbor")
    ).expanduser().resolve()


@dataclass(frozen=True)
class Package:
    url: str
    filename: str
    size: int
    sha256: str

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9.+%~:_-]+\.deb", self.filename):
            raise ValueError(f"Unsafe package filename: {self.filename!r}")
        if type(self.size) is not int or self.size <= 0:
            raise ValueError("Package size must be a positive integer")
        if not re.fullmatch(r"[a-f0-9]{64}", self.sha256):
            raise ValueError("Package requires a SHA256 digest")

    def verify(self, path: Path) -> None:
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if path.stat().st_size != self.size or digest != self.sha256:
            raise ValueError(f"Package checksum/size mismatch: {self.filename}")


def parse_apt_plan(stdout: str) -> list[Package]:
    packages = []
    for line in stdout.splitlines():
        if not line.startswith("'"):
            continue
        url, filename, size, digest = shlex.split(line)
        if not digest.startswith("SHA256:"):
            raise ValueError("APT download plan did not provide SHA256 hashes")
        packages.append(
            Package(url, filename, int(size), digest.removeprefix("SHA256:"))
        )
    return packages


class AptCache:
    """Key downloads by their APT-index hash, never by a mutable package name."""

    def __init__(self, root: Path):
        self.root = root

    def path(self, package: Package) -> Path:
        return self.root / "apt" / package.sha256 / package.filename

    def store(self, package: Package, source: Path) -> None:
        package.verify(source)
        target = self.path(package)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic publication also supports concurrent trials sharing this cache.
        with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
            staged = Path(temporary) / package.filename
            shutil.copyfile(source, staged)
            package.verify(staged)
            staged.replace(target)

    def import_manifest(self, manifest: Path) -> int:
        packages = [Package(**row) for row in json.loads(manifest.read_text())]
        for package in packages:
            package.verify(manifest.parent / "packages" / package.filename)
        for package in packages:
            self.store(package, manifest.parent / "packages" / package.filename)
        return len(packages)

    async def install(
        self, agent, environment, packages: tuple[str, ...], record: dict,
    ) -> None:
        """Restore only files selected by the current index; let APT install them.

        Download before installation so Docker's APT cleanup hooks cannot remove
        successful downloads before they enter the shared cache.
        """
        args = shlex.join(packages)
        env = {"DEBIAN_FRONTEND": "noninteractive"}
        await agent.exec_as_root(environment, command="apt-get update", env=env)
        result = await agent.exec_as_root(
            environment,
            command=(
                "apt-get -o Acquire::ForceHash=sha256 --print-uris "
                f"-y --download-only install {args}"
            ),
            env=env,
        )
        plan = parse_apt_plan(result.stdout)
        attempt = {
            "requested": list(packages), "packages": [asdict(p) for p in plan],
            "restored": [], "saved": [],
        }
        record.setdefault("apt", []).append(attempt)
        for package in plan:
            cached = self.path(package)
            if cached.exists():
                package.verify(cached)
                await environment.upload_file(
                    cached, f"/var/cache/apt/archives/{package.filename}",
                )
                attempt["restored"].append(package.filename)
        await agent.exec_as_root(
            environment, command=f"apt-get -y --download-only install {args}", env=env,
        )
        with tempfile.TemporaryDirectory(prefix="nanopy-apt-") as temporary:
            for package in plan:
                if package.filename in attempt["restored"]:
                    continue
                downloaded = Path(temporary) / package.filename
                await environment.download_file(
                    source_path=f"/var/cache/apt/archives/{package.filename}",
                    target_path=downloaded,
                )
                self.store(package, downloaded)
                attempt["saved"].append(package.filename)
        await agent.exec_as_root(
            environment, command=f"apt-get install -y {args}", env=env,
        )


# Profiles describe dependencies only. Neither task solutions nor assertions are
# loaded during setup. A task revision change requires reviewing its profile.
QEMU_TASK = "terminal-bench/qemu-alpine-ssh"
QEMU_REF = "sha256:60b7050b0e0aa51641208cf65766743d340e59575db2c4d2f8628240846c2a28"
QEMU_PREFLIGHT = (
    "set -euo pipefail; "
    "curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh; "
    'export PATH="$HOME/.local/bin:$PATH"; '
    "uv --version | grep -Eq '^uv 0\\.9\\.5( |$)'; "
    "command -v sshpass; "
    "uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 pytest --version"
)
PYTORCH_RECOVERY_TASK = "terminal-bench/pytorch-model-recovery"
PYTORCH_RECOVERY_REF = "sha256:2e628841cff93290919172398e573e794f34c95d9382b7425adde4364022decc"
PYTORCH_RECOVERY_PREFLIGHT = (
    "set -euo pipefail; cd /tmp; command -v curl; "
    "curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh; "
    'export PATH="$HOME/.local/bin:$PATH"; '
    "uv --version | grep -Eq '^uv 0\\.9\\.5( |$)'; "
    "uvx -p 3.13 -w pytest==8.4.1 -w torch==2.7.1 "
    "-w pytest-json-ctrf==0.3.5 pytest --version"
)


@dataclass(frozen=True)
class VerifierProfile:
    name: str
    apt_packages: tuple[str, ...]
    command: str
    task_files_sha256: tuple[tuple[str, str], ...] = ()


def python_verifier_command(requirements: tuple[str, ...], *, indexes=()) -> str:
    """Warm a reviewed uvx environment without importing task code or tests."""
    return (
        "set -euo pipefail; cd /tmp; command -v curl; "
        "curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh; "
        'export PATH="$HOME/.local/bin:$PATH"; '
        "uv --version | grep -Eq '^uv 0\\.9\\.5( |$)'; "
        + shlex.join([
            "uvx", *indexes, "-p", "3.13",
            *[arg for requirement in requirements for arg in ("-w", requirement)],
            "pytest", "--version",
        ])
    )


VERIFIER_PROFILES = {
    (QEMU_TASK, QEMU_REF): VerifierProfile(
        "qemu-alpine-ssh-v1", ("curl", "sshpass"), QEMU_PREFLIGHT,
    ),
    (PYTORCH_RECOVERY_TASK, PYTORCH_RECOVERY_REF): VerifierProfile(
        "pytorch-model-recovery-v1", ("curl",), PYTORCH_RECOVERY_PREFLIGHT,
        (("task.toml", "851a51204f53482a31f47cdf8833128cf421113b0331011286940fc857c37dfd"),
         ("tests/test.sh", "6005f3a75ccfe00d7bed1005264b4a84a1f8e30cd780f8a97b3a804be7cc7a8e")),
    ),
    ("terminal-bench/multi-source-data-merger",
     "sha256:70367c38732e1beda7b229968a48d60242277c2fa4db91339c3f064c4c230d49"): VerifierProfile(
        "multi-source-data-merger-v1", ("curl",), python_verifier_command((
            "pytest==8.4.1", "pandas==2.3.3", "pyarrow==22.0.0", "pytest-json-ctrf==0.3.5",
        )),
        (("task.toml", "ee3964c0ee040f0a0cb121cefefbc15443d127684acb003fa5b61dd42f31c694"),
         ("tests/test.sh", "d5a00e64413c0e1ae452f38a1aa1a47c3ed7b4416bbfccae1a4c053025a336d1")),
    ),
    ("terminal-bench/pytorch-model-cli",
     "sha256:6f11544dcc81a380dc4611902961f5520259c462d9fceb413419d66ab9a96c79"): VerifierProfile(
        "pytorch-model-cli-v1", ("curl", "ffmpeg", "libsm6", "libxext6"),
        python_verifier_command((
            "torch==2.7.1", "torchvision==0.22.1", "numpy==2.3.1",
            "opencv-python==4.11.0.86", "pytest==8.4.1", "pytest-json-ctrf==0.3.5",
        ), indexes=("--index", "https://download.pytorch.org/whl/cpu",
                    "--index-strategy", "unsafe-best-match")),
        (("task.toml", "fc1c018efbd5d0537ac0741d53d1ebad3886faa51d14cbde8ec953856411bc0d"),
         ("tests/test.sh", "43fb67e537c7adc2df11c2367f47c876cb5d16a7c1ae16d0339c3a3364bb2b06")),
    ),
    ("terminal-bench/query-optimize",
     "sha256:169496ea6843cb403b0860132675baf7aa0df0ac8b86221068e27d86395260f4"): VerifierProfile(
        "query-optimize-v1", ("curl",), python_verifier_command((
            "pytest==8.4.1", "pytest-json-ctrf==0.3.5",
        )),
        (("task.toml", "6e88f2a86df699594bcb1bf81df4ed694505f79c9420f671335b02524bbe3868"),
         ("tests/test.sh", "4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334")),
    ),
    ("terminal-bench/torch-pipeline-parallelism",
     "sha256:db605337c749a872cea7b5b413429b3915bb4c3efe0f7875f0c46ce81bd8c4fb"): VerifierProfile(
        "torch-pipeline-parallelism-v1", ("curl",), python_verifier_command((
            "pytest==8.4.1", "torch==2.7.0", "transformers==4.55.0", "pytest-json-ctrf==0.3.5",
        )),
        (("task.toml", "8b4f9f525c08afbbc4eca9168e46238a61ccb903486773e9ca4da64bb7ffe857"),
         ("tests/test.sh", "cc9fd28b6590993fc37e4a99da771cbf04726c8c62fe308e802612241da69dea")),
    ),
    ("terminal-bench/torch-tensor-parallelism",
     "sha256:f32ce74a5aeb6638480247ab799fe46127bbee631acdd0921b0f394ec49b3684"): VerifierProfile(
        "torch-tensor-parallelism-v1", ("curl",), python_verifier_command((
            "pytest==8.4.1", "torch==2.7.0", "pytest-json-ctrf==0.3.5",
        )),
        (("task.toml", "72fd2a5500d1fe8795dcae76cccb1a29fb25894881a7475f2fa519c87d425a8d"),
         ("tests/test.sh", "a7e6c9408b2401e4e7448371f7ddc72f3284caccfb56277d3cd4e98051868cdf")),
    ),
}


def verifier_profile(
    logs_dir: Path, environment_name: str | None,
) -> VerifierProfile | None:
    known_tasks = {name for name, _ in VERIFIER_PROFILES}
    known_environment = environment_name in {name.split("/")[-1] for name in known_tasks}
    config_path = logs_dir.parent / "config.json"
    if not config_path.exists():
        if known_environment:
            raise ValueError("Verifier preflight requires Harbor's pinned trial config")
        return None
    task = json.loads(config_path.read_text())["task"]
    profile = VERIFIER_PROFILES.get((task.get("name"), task.get("ref")))
    # Local and Git datasets omit package name/ref. The environment identifies
    # a known task, but cannot establish its reviewed revision by itself.
    if profile is None and (task.get("name") in known_tasks or known_environment):
        name = task.get("name") if task.get("name") in known_tasks else environment_name
        raise ValueError(
            f"Unknown {name} revision; review its verifier dependency profile"
        )
    return profile
