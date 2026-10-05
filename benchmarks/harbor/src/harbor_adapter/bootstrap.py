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


@dataclass(frozen=True)
class VerifierProfile:
    name: str
    apt_packages: tuple[str, ...]
    command: str


VERIFIER_PROFILES = {
    (QEMU_TASK, QEMU_REF): VerifierProfile(
        "qemu-alpine-ssh-v1", ("curl", "sshpass"), QEMU_PREFLIGHT,
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
