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
