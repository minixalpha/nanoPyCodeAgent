"""Integrity checks for optional, content-preserving image cache imports."""

import gzip
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest


spec = importlib.util.spec_from_file_location(
    "cache_image", Path(__file__).parents[1] / "scripts/cache_image.py",
)
cache_image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache_image)


def descriptor(data, media_type="application/octet-stream"):
    return {"digest": cache_image.sha(data), "size": len(data), "mediaType": media_type}


def put(cache, data, media_type):
    desc = descriptor(data, media_type)
    path = cache_image.blob_path(cache, desc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return desc


def fixture_manifest(cache, diff_id=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        entry = tarfile.TarInfo("example.txt")
        entry.size = 5
        archive.addfile(entry, io.BytesIO(b"hello"))
    layer = stream.getvalue()
    compressed = gzip.compress(layer)
    config = json.dumps({
        "os": "linux", "architecture": "amd64",
        "rootfs": {"type": "layers", "diff_ids": [diff_id or cache_image.sha(layer)]},
    }).encode()
    return json.dumps({
        "schemaVersion": 2, "mediaType": cache_image.MANIFEST_TYPES[0],
        "config": put(cache, config, "application/vnd.docker.container.image.v1+json"),
        "layers": [put(cache, compressed, "application/vnd.docker.image.rootfs.diff.tar.gzip")],
    }).encode()


def test_parallel_ranges_reconstruct_original_blob(tmp_path, monkeypatch):
    payload = b"0123456789abcdefghij"
    requests = []

    def get(url, headers, limit):
        requested = headers["Range"].removeprefix("bytes=")
        start, end = map(int, requested.split("-"))
        requests.append((start, end))
        return 206, {"Content-Range": f"bytes {start}-{end}/{len(payload)}"}, payload[start:end + 1]

    monkeypatch.setattr(cache_image, "get", get)
    path = cache_image.fetch_blob(tmp_path, descriptor(payload), "unused", {}, workers=2, chunk_size=6)
    assert path.read_bytes() == payload
    assert sorted(requests) == [(0, 5), (6, 11), (12, 17), (18, 19)]
    requests.clear()
    cache_image.fetch_blob(tmp_path, descriptor(payload), "unused", {})
    assert requests == []


@pytest.mark.parametrize("status,content_range,body", [
    (200, None, b"abc"),
    (206, "bytes 3-5/6", b"abc"),
    (206, "bytes 0-2/6", b"ab"),
])
def test_reject_inexact_or_truncated_ranges(tmp_path, monkeypatch, status, content_range, body):
    monkeypatch.setattr(cache_image, "get", lambda *args: (status, {"Content-Range": content_range}, body))
    with pytest.raises(ValueError):
        cache_image.fetch_blob(tmp_path, descriptor(b"abcdef"), "unused", {}, chunk_size=3)
    assert not cache_image.blob_path(tmp_path, descriptor(b"abcdef")).exists()


def test_reject_corrupt_complete_download(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_image, "get", lambda *args: (200, {}, b"abd"))
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        cache_image.fetch_blob(tmp_path, descriptor(b"abc"), "unused", {})
    assert not cache_image.blob_path(tmp_path, descriptor(b"abc")).exists()


def test_retry_short_transport_response_before_caching(tmp_path, monkeypatch):
    replies = iter([(200, {}, b"ab"), (200, {}, b"abc")])
    monkeypatch.setattr(cache_image, "get", lambda *args: next(replies))
    path = cache_image.fetch_blob(tmp_path, descriptor(b"abc"), "unused", {})
    assert path.read_bytes() == b"abc"


def test_revalidate_cached_bytes(tmp_path):
    desc = put(tmp_path, b"abc", "application/octet-stream")
    path = cache_image.blob_path(tmp_path, desc)
    path.write_bytes(b"abd")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        cache_image.fetch_blob(tmp_path, desc, "unused", {})
    path.write_bytes(b"ab")
    with pytest.raises(ValueError, match="size mismatch"):
        cache_image.fetch_blob(tmp_path, desc, "unused", {})


def test_archive_preserves_manifest_and_all_blobs(tmp_path):
    raw = fixture_manifest(tmp_path)
    output = tmp_path / "image.tar"
    cache_image.write_archive(tmp_path, "example/task:version", raw, output)
    with tarfile.open(output) as archive:
        index = json.load(archive.extractfile("index.json"))
        reference = index["manifests"][0]
        assert reference["digest"] == cache_image.sha(raw)
        assert reference["annotations"]["io.containerd.image.name"] == "docker.io/example/task:version"
        assert archive.extractfile("blobs/sha256/" + reference["digest"].split(":")[1]).read() == raw
        manifest = json.loads(raw)
        for desc in [manifest["config"], *manifest["layers"]]:
            data = archive.extractfile("blobs/sha256/" + desc["digest"].split(":")[1]).read()
            assert cache_image.sha(data) == desc["digest"]


def test_reject_mismatched_uncompressed_layer(tmp_path):
    raw = fixture_manifest(tmp_path, cache_image.sha(b"different layer"))
    with pytest.raises(ValueError, match="Uncompressed layer SHA256"):
        cache_image.write_archive(tmp_path, "example/task:version", raw, tmp_path / "image.tar")
    assert not (tmp_path / "image.tar").exists()


@pytest.mark.parametrize("digest", ["sha256:../../bad", "md5:abcd", "sha256:ABCDEF"])
def test_reject_unsafe_or_unsupported_blob_paths(tmp_path, digest):
    with pytest.raises(ValueError, match="Only SHA256"):
        cache_image.blob_path(tmp_path, {"digest": digest, "size": 1})


def test_changed_tag_is_rejected_before_downloading_blobs(tmp_path, monkeypatch):
    raw = fixture_manifest(tmp_path)
    (tmp_path / "example_task_version.json").write_text(json.dumps({"manifest_digest": "old"}))
    replies = iter([
        (200, {}, b'{"token":"anonymous-read-token"}'),
        (200, {"Docker-Content-Digest": cache_image.sha(raw)}, raw),
    ])
    monkeypatch.setattr(cache_image, "get", lambda *args: next(replies))
    with pytest.raises(ValueError, match="Image tag changed"):
        cache_image.cache_image("example/task:version", tmp_path)


def test_redirect_does_not_forward_registry_authorization():
    request = cache_image.Request("https://registry-1.docker.io/blob", headers={"Authorization": "Bearer token", "Range": "bytes=0-2"})
    redirected = cache_image.SafeRedirect().redirect_request(request, None, 307, "", {}, "https://cdn.docker.com/blob")
    assert not redirected.has_header("Authorization")
    assert redirected.get_header("Range") == "bytes=0-2"
    with pytest.raises(ValueError, match="HTTPS"):
        cache_image.SafeRedirect().redirect_request(request, None, 307, "", {}, "http://cdn.docker.com/blob")


def test_registry_refreshes_expiring_token_before_later_ranges(monkeypatch):
    clock = [0]
    tokens = []
    def get(url, headers=None, limit=None):
        if url.startswith("https://auth.docker.io/"):
            token = f"token-{len(tokens)}"
            tokens.append(token)
            return 200, {}, json.dumps({"token": token, "expires_in": 300}).encode()
        return 206, {}, headers["Authorization"].encode()
    monkeypatch.setattr(cache_image, "get", get)
    monkeypatch.setattr(cache_image.time, "monotonic", lambda: clock[0])
    auth = cache_image.RegistryAuth("example/task")
    assert auth.get("blob")[2] == b"Bearer token-0"
    clock[0] = 271
    assert auth.get("blob")[2] == b"Bearer token-1"
    assert len(tokens) == 2


def test_registry_refreshes_once_on_unauthorized_and_preserves_range(monkeypatch):
    calls = []
    tokens = iter(["old", "new"])
    def get(url, headers=None, limit=None):
        if url.startswith("https://auth.docker.io/"):
            return 200, {}, json.dumps({"token": next(tokens)}).encode()
        calls.append(headers.copy())
        if headers["Authorization"] == "Bearer old":
            raise cache_image.RegistryHTTPError(401)
        return 206, {}, b"abc"
    monkeypatch.setattr(cache_image, "get", get)
    assert cache_image.RegistryAuth("example/task").get("blob", {"Range": "bytes=0-2"})[2] == b"abc"
    assert [call["Range"] for call in calls] == ["bytes=0-2", "bytes=0-2"]


def test_registry_does_not_refresh_indefinitely_or_on_rate_limits(monkeypatch):
    for status, expected_calls in [(401, 2), (429, 1)]:
        calls = []
        def get(url, headers=None, limit=None):
            if url.startswith("https://auth.docker.io/"):
                return 200, {}, b'{"token":"token"}'
            calls.append(url)
            raise cache_image.RegistryHTTPError(status)
        monkeypatch.setattr(cache_image, "get", get)
        with pytest.raises(cache_image.RegistryHTTPError) as error:
            cache_image.RegistryAuth("example/task").get("blob")
        assert error.value.status == status
        assert len(calls) == expected_calls


def test_http_diagnostic_does_not_expose_signed_url(monkeypatch):
    secret_url = "https://cdn.example/blob?signature=private"
    class Opener:
        def open(self, *args, **kwargs):
            raise cache_image.HTTPError(secret_url, 401, "unauthorized", {}, None)
    monkeypatch.setattr(cache_image, "build_opener", lambda *args: Opener())
    with pytest.raises(cache_image.RegistryHTTPError) as error:
        cache_image.get(secret_url)
    assert str(error.value) == "Registry request failed: HTTP 401"
    assert "private" not in str(error.value)


def fixture_index(raw, platforms=None):
    child = descriptor(raw, cache_image.MANIFEST_TYPES[0])
    platforms = platforms or [{"os": "linux", "architecture": "amd64"}, {"os": "linux", "architecture": "arm64"}]
    return json.dumps({"schemaVersion": 2, "mediaType": cache_image.INDEX_TYPES[1],
                       "manifests": [{**child, "platform": platform} for platform in platforms]}).encode()


def test_index_archive_preserves_parent_child_and_native_layers(tmp_path):
    raw = fixture_manifest(tmp_path)
    index = fixture_index(raw)
    output = tmp_path / "indexed.tar"
    cache_image.write_archive(tmp_path, "example/task:version", raw, output, root_index=index)
    with tarfile.open(output) as archive:
        reference = json.load(archive.extractfile("index.json"))["manifests"][0]
        assert reference["digest"] == cache_image.sha(index)
        assert archive.extractfile("blobs/sha256/" + cache_image.sha(index).split(":")[1]).read() == index
        assert archive.extractfile("blobs/sha256/" + cache_image.sha(raw).split(":")[1]).read() == raw
        for item in json.loads(raw)["layers"]:
            assert cache_image.sha(archive.extractfile("blobs/sha256/" + item["digest"].split(":")[1]).read()) == item["digest"]


@pytest.mark.parametrize("platforms", [
    [{"os": "linux", "architecture": "arm64"}],
    [{"os": "linux", "architecture": "amd64"}] * 2,
    [{"os": "linux", "architecture": "amd64", "variant": "v3"}],
    [{"os": "windows", "architecture": "amd64"}],
])
def test_index_rejects_missing_or_ambiguous_native_platform(platforms):
    with pytest.raises(ValueError, match="exactly one Linux amd64"):
        cache_image.native_descriptor(json.loads(fixture_index(b"child", platforms)))


def test_index_rejects_a_different_native_manifest(tmp_path):
    raw = fixture_manifest(tmp_path)
    with pytest.raises(ValueError, match="differs from its original index"):
        cache_image.write_archive(tmp_path, "example/task:version", raw, tmp_path / "image.tar",
                                  root_index=fixture_index(b"different manifest"))
    assert not (tmp_path / "image.tar").exists()


def test_registry_index_loads_selected_child_by_digest_and_keeps_parent_pin(tmp_path, monkeypatch):
    raw = fixture_manifest(tmp_path)
    index = fixture_index(raw)
    requests = []
    def get(url, headers=None, limit=None):
        requests.append(url)
        if url.startswith("https://auth.docker.io/"):
            return 200, {}, b'{"token":"anonymous-token"}'
        body = index if url.endswith("/version") else raw
        return 200, {"Docker-Content-Digest": cache_image.sha(body)}, body
    monkeypatch.setattr(cache_image, "get", get)
    cache_image.cache_image("example/task:version", tmp_path)
    assert requests[-1].endswith("/manifests/" + cache_image.sha(raw))
    lock = json.loads((tmp_path / "example_task_version.json").read_text())
    assert lock["manifest_digest"] == cache_image.sha(index)
    with tarfile.open(tmp_path / "example_task_version.oci.tar") as archive:
        assert json.load(archive.extractfile("index.json"))["manifests"][0]["digest"] == cache_image.sha(index)
