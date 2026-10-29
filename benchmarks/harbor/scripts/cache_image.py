"""Cache an unchanged public Docker Hub image through verified HTTP ranges.

For slow or interrupted Docker pulls, create an OCI archive, then optionally
load it into Docker's containerd image store. No layers are edited or rebuilt.
Linux amd64 images with SHA256 and gzip layers are supported. OCI indexes and
Docker manifest lists retain their original bytes while loading that platform.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import gzip
import hashlib
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MANIFEST_TYPES = (
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
)
INDEX_TYPES = (
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.index.v1+json",
)
LAYER_TYPES = {
    "application/vnd.docker.image.rootfs.diff.tar.gzip",
    "application/vnd.oci.image.layer.v1.tar+gzip",
}


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        if urlsplit(url).scheme != "https":
            raise ValueError("Registry redirects must retain HTTPS")
        redirected = super().redirect_request(request, response, code, message, headers, url)
        if urlsplit(url).netloc != urlsplit(request.full_url).netloc:
            redirected.remove_header("Authorization")
        return redirected


class RegistryHTTPError(RuntimeError):
    """Report an HTTP status without leaking signed URLs or request headers."""

    def __init__(self, status):
        self.status = status
        super().__init__(f"Registry request failed: HTTP {status}")


def get(url, headers=None, limit=4 * 1024 * 1024):
    # Never include exception URLs: blob redirects may contain signed queries.
    for attempt in range(3):
        try:
            with build_opener(SafeRedirect()).open(Request(url, headers=headers or {}), timeout=30) as r:
                data = r.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("Response exceeds requested size")
                return r.status, dict(r.headers.items()), data
        except HTTPError as error:
            if error.code == 401 or attempt == 2:
                raise RegistryHTTPError(error.code) from None
            time.sleep(attempt + 1)
        except (URLError, TimeoutError, OSError, IncompleteRead) as error:
            if attempt == 2:
                raise RuntimeError(f"Registry request failed: {type(error).__name__}") from None
            time.sleep(attempt + 1)


class RegistryAuth:
    """Refresh anonymous pull tokens during long, parallel range downloads."""

    def __init__(self, repository):
        self.url = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:" + repository + ":pull"
        self._token = None
        self._expires_at = 0
        self._lock = threading.Lock()

    def token(self, rejected=None):
        with self._lock:
            if rejected is not None and rejected == self._token:
                self._expires_at = 0
            if self._token is None or time.monotonic() >= self._expires_at:
                _, _, raw = get(self.url)
                data = json.loads(raw)
                token = data.get("token") or data.get("access_token")
                if not isinstance(token, str) or not token:
                    raise ValueError("Registry did not return a pull token")
                self._token = token
                self._expires_at = time.monotonic() + max(1, float(data.get("expires_in", 300)) - 30)
            return self._token

    def get(self, url, headers=None, limit=4 * 1024 * 1024):
        rejected = None
        for attempt in range(2):
            token = self.token(rejected)
            request_headers = {
                "Accept": ", ".join((*MANIFEST_TYPES, *INDEX_TYPES)), **(headers or {}),
                "Authorization": "Bearer " + token,
            }
            try:
                return get(url, request_headers, limit)
            except RegistryHTTPError as error:
                if error.status != 401 or attempt:
                    raise
                rejected = token


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def blob_path(cache, descriptor):
    digest = descriptor["digest"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Only SHA256 descriptors are supported")
    if not isinstance(descriptor["size"], int) or descriptor["size"] < 0:
        raise ValueError("Invalid descriptor size")
    return cache / "blobs/sha256" / digest.split(":")[1]


def verify(path, descriptor):
    if path.stat().st_size != descriptor["size"]:
        raise ValueError("Blob size mismatch")
    with path.open("rb") as stream:
        actual = "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != descriptor["digest"]:
        raise ValueError("Blob SHA256 mismatch")


def fetch_blob(cache, descriptor, url, headers, workers=8, chunk_size=1024 * 1024, *, request=None):
    request = request or get
    path = blob_path(cache, descriptor)
    if path.exists():
        verify(path, descriptor)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = cache / "parts" / path.name
    parts.mkdir(parents=True, exist_ok=True)
    size = descriptor["size"]

    def fetch(start):
        end = min(start + chunk_size, size) - 1
        part = parts / str(start)
        if part.exists() and part.stat().st_size == end - start + 1:
            return part
        for attempt in range(3):
            status, response_headers, data = request(
                url, {**headers, "Range": f"bytes={start}-{end}"}, end - start + 1,
            )
            response_headers = {k.lower(): v for k, v in response_headers.items()}
            complete = start == 0 and end == size - 1 and status == 200
            expected_range = f"bytes {start}-{end}/{size}"
            if not complete and (status != 206 or response_headers.get("content-range") != expected_range):
                raise ValueError("Server did not return the exact requested range")
            if len(data) == end - start + 1:
                break
        else:
            raise ValueError("Incomplete range response")
        temporary = part.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(part)
        return part

    with ThreadPoolExecutor(max_workers=workers) as pool:
        downloaded = list(pool.map(fetch, range(0, size, chunk_size)))
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as out:
        for part in downloaded:
            out.write(part.read_bytes())
    verify(temporary, descriptor)
    temporary.replace(path)
    for part in downloaded:
        part.unlink()
    parts.rmdir()
    return path


def validate_layers(cache, manifest):
    config = json.loads(blob_path(cache, manifest["config"]).read_bytes())
    if config.get("os") != "linux" or config.get("architecture") != "amd64":
        raise ValueError("Only Linux amd64 images are supported")
    diff_ids = config["rootfs"]["diff_ids"]
    if config["rootfs"].get("type") != "layers":
        raise ValueError("Unsupported root filesystem configuration")
    if len(diff_ids) != len(manifest["layers"]):
        raise ValueError("Layer count differs from image configuration")
    for layer, expected in zip(manifest["layers"], diff_ids):
        if layer["mediaType"] not in LAYER_TYPES:
            raise ValueError("Only gzip layers are supported")
        with gzip.open(blob_path(cache, layer), "rb") as stream:
            actual = "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Uncompressed layer SHA256 differs from image configuration")
    return config


def native_descriptor(index):
    """Select exactly one explicit Linux amd64 child without changing its index."""
    if index.get("schemaVersion") != 2 or index.get("mediaType") not in INDEX_TYPES:
        raise ValueError("Expected a schema 2 OCI index or Docker manifest list")
    matches = [item for item in index.get("manifests", []) if (
        item.get("platform", {}).get("os") == "linux"
        and item.get("platform", {}).get("architecture") == "amd64"
        and item.get("platform", {}).get("variant") in {None, "", "v1"}
    )]
    if len(matches) != 1 or matches[0].get("mediaType") not in MANIFEST_TYPES:
        raise ValueError("Image index requires exactly one Linux amd64 image manifest")
    blob_path(Path("."), matches[0])
    return matches[0]


def write_archive(cache, image, raw_manifest, output, *, root_index=None):
    manifest = json.loads(raw_manifest)
    if manifest.get("schemaVersion") != 2 or manifest.get("mediaType") not in MANIFEST_TYPES:
        raise ValueError("Only single-platform schema 2 image manifests are supported")
    descriptors = [manifest["config"], *manifest["layers"]]
    for descriptor in descriptors:
        verify(blob_path(cache, descriptor), descriptor)
    validate_layers(cache, manifest)
    manifest_descriptor = {"mediaType": manifest["mediaType"], "size": len(raw_manifest), "digest": sha(raw_manifest)}
    manifest_path = blob_path(cache, manifest_descriptor)
    manifest_path.write_bytes(raw_manifest)
    descriptors.append(manifest_descriptor)
    reference = manifest_descriptor
    if root_index is not None:
        index = json.loads(root_index)
        selected = native_descriptor(index)
        if selected["digest"] != sha(raw_manifest) or selected["size"] != len(raw_manifest):
            raise ValueError("Selected image manifest differs from its original index")
        reference = {"mediaType": index["mediaType"], "size": len(root_index), "digest": sha(root_index)}
        blob_path(cache, reference).write_bytes(root_index)
        descriptors.append(reference)
    index = {"schemaVersion": 2, "manifests": [{
        **reference, "annotations": {
            "io.containerd.image.name": "docker.io/" + image,
            "org.opencontainers.image.ref.name": image.rsplit(":", 1)[1],
        },
    }]}
    temporary = output.with_suffix(".tmp")
    with tarfile.open(temporary, "w") as archive:
        for name, data in (
            ("oci-layout", b'{"imageLayoutVersion":"1.0.0"}'),
            ("index.json", json.dumps(index).encode()),
        ):
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
        seen = set()
        for descriptor in descriptors:
            path = blob_path(cache, descriptor)
            if path not in seen:
                archive.add(path, arcname=str(path.relative_to(cache)), recursive=False)
                seen.add(path)
    temporary.replace(output)


def cache_image(image, cache, workers=8, load=False):
    if not re.fullmatch(r"[a-z0-9_-]+/[a-z0-9._-]+:[A-Za-z0-9._-]+", image):
        raise ValueError("Expected a public Docker Hub owner/repository:tag")
    cache.mkdir(parents=True, exist_ok=True)
    repo, tag = image.rsplit(":", 1)
    auth = RegistryAuth(repo)
    base = "https://registry-1.docker.io/v2/" + repo
    _, response_headers, raw = auth.get(base + "/manifests/" + tag)
    response_headers = {k.lower(): v for k, v in response_headers.items()}
    if response_headers.get("docker-content-digest") != sha(raw):
        raise ValueError("Registry manifest digest mismatch")
    manifest = json.loads(raw)
    root_index = None
    root_digest = sha(raw)
    if manifest.get("mediaType") in INDEX_TYPES:
        root_index = raw
        selected = native_descriptor(manifest)
        _, child_headers, raw = auth.get(base + "/manifests/" + selected["digest"])
        child_headers = {k.lower(): v for k, v in child_headers.items()}
        if (len(raw) != selected["size"] or sha(raw) != selected["digest"]
                or child_headers.get("docker-content-digest") != selected["digest"]):
            raise ValueError("Native image manifest size or digest differs from its index")
        manifest = json.loads(raw)
    if manifest.get("mediaType") not in MANIFEST_TYPES or manifest.get("schemaVersion") != 2:
        raise ValueError("Only schema 2 image manifests and native-platform indexes are supported")
    lock = {"image": image, "manifest_digest": root_digest, "config_digest": manifest["config"]["digest"]}
    lock_path = cache / (image.replace("/", "_").replace(":", "_") + ".json")
    if lock_path.exists() and json.loads(lock_path.read_text()) != lock:
        raise ValueError("Image tag changed since the first cache request")
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print(json.dumps(lock), flush=True)
    for descriptor in [manifest["config"], *manifest["layers"]]:
        fetch_blob(cache, descriptor, base + "/blobs/" + descriptor["digest"], {}, workers, request=auth.get)
        print(json.dumps({"verified_blob": descriptor["digest"], "bytes": descriptor["size"]}), flush=True)
    output = cache / (lock_path.stem + ".oci.tar")
    write_archive(cache, image, raw, output, root_index=root_index)
    if load:
        driver = subprocess.check_output(["docker", "info", "--format", "{{json .DriverStatus}}"], text=True)
        if "io.containerd.snapshotter.v1" not in driver:
            raise ValueError("OCI import requires Docker's containerd image store")
        platform = ["--platform", "linux/amd64"] if root_index is not None else []
        subprocess.run(["docker", "load", "--quiet", *platform, "--input", str(output)], check=True)
        installed = json.loads(subprocess.check_output(["docker", "image", "inspect", image], text=True))[0]
        if not any(ref.endswith("@" + lock["manifest_digest"]) for ref in installed["RepoDigests"]):
            raise ValueError("Imported image does not retain the original manifest digest")
    print(json.dumps({"archive": str(output), "loaded": load, **lock}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    with (args.cache / ".writer.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cache_image(args.image, args.cache, args.workers, args.load)


if __name__ == "__main__":
    main()
