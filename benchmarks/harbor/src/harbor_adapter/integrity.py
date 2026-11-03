"""Versioned evaluation rules shared by every repository adapter."""

from functools import wraps
import hashlib
from ipaddress import ip_address
import json
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

from harbor.models.task.config import NetworkPolicy, normalize_allowed_hosts


RULES = """Evaluation integrity rules (restricted-v1):
Solve the task using the supplied workspace, task inputs, and permitted general
documentation or dependencies. You may read tests supplied with the workspace
and write and run your own tests. Do not retrieve task-specific benchmark
solutions, hidden tests, answer keys, original benchmark inputs absent from the
workspace, or other agents' outputs, whether from the internet or local files.
Do not change, impersonate, or interfere with the verifier, its dependencies,
logs, reward files, or evaluation controls. Do not leave a process that watches
for hidden tests or alters the submission during verification. Network access
is restricted by the evaluation environment. A blocked request is not permission
to bypass the restriction. Report missing resources instead.
"""
RULES_SHA256 = hashlib.sha256(RULES.encode()).hexdigest()


class IntegrityPolicy(BaseModel):
    """Explicit hosts, never a silently widened provider or package allowlist."""

    model_config = ConfigDict(extra="forbid", strict=True)
    protocol: Literal["restricted-v1"] = "restricted-v1"
    allowed_hosts: list[str] = Field(min_length=1)
    # A positive control before restriction, then a negative control after it.
    probe_url: str = "https://example.com/"

    @field_validator("allowed_hosts")
    @classmethod
    def exact_hosts(cls, hosts):
        hosts = normalize_allowed_hosts(hosts)
        for host in hosts:
            if "*" in host or "/" in host:
                raise ValueError("Integrity allowlists require exact hosts, not wildcards or networks")
            try:
                ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("Use explicit DNS hosts, not IP literals, in integrity allowlists")
        return sorted(set(hosts))

    @field_validator("probe_url")
    @classmethod
    def public_probe(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or parsed.port not in (None, 443)):
            raise ValueError("probe_url must be a credential-free HTTPS URL on port 443")
        return value

    def network(self):
        if urlsplit(self.probe_url).hostname in self.allowed_hosts:
            raise ValueError("The negative-control probe must not be allowlisted")
        return NetworkPolicy(network_mode="allowlist", allowed_hosts=self.allowed_hosts)


def write_record(path: Path, value: dict) -> None:
    """Keep host evidence private, including logs that may contain credentials."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        temporary.chmod(0o600)
        json.dump(value, output, indent=2)
        output.write("\n")
    temporary.replace(path)


def integrity_run(run):
    """Guard the common run boundary without changing an agent's native tools."""
    @wraps(run)
    async def guarded(self, instruction, environment, context):
        if self._integrity_policy is None:
            return await run(self, instruction, environment, context)
        from .integrity_environment import IntegrityDockerEnvironment

        if not isinstance(environment, IntegrityDockerEnvironment):
            raise ValueError("Integrity runs require IntegrityDockerEnvironment")
        if environment.integrity_policy != self._integrity_policy:
            raise ValueError("Agent and environment integrity policies differ")
        async with environment.agent_phase():
            return await run(self, RULES + "\nTask:\n" + instruction, environment, context)
    return guarded
