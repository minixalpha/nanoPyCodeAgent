"""The optional uv cache serves only archives bound to original release metadata."""

import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import threading

import pytest

spec = importlib.util.spec_from_file_location(
    "uv_release_cache", Path(__file__).parents[1] / "scripts/uv_release_cache.py",
)
uv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uv)


def metadata(payload=b"original uv archive", version="0.9.11"):
    return json.dumps({"tag_name": version, "assets": [{
        "name": uv.ASSET, "size": len(payload),
        "digest": "sha256:" + hashlib.sha256(payload).hexdigest(), "id": 123,
        "browser_download_url": "https://github.com" + uv.asset_path(version),
    }]}).encode()


def make_cache(tmp_path, payload=b"original uv archive"):
    raw = metadata(payload)
    entry = uv.release_asset("0.9.11", raw)
    (tmp_path / "metadata").mkdir()
    (tmp_path / "metadata" / (entry["release_metadata_sha256"] + ".json")).write_bytes(raw)
    blob = uv.ranges.blob_path(tmp_path, entry)
    blob.parent.mkdir(parents=True)
    blob.write_bytes(payload)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"assets": [entry]}))
    return manifest, blob


@pytest.mark.parametrize("field,value", [
    ("name", "other.tar.gz"), ("size", 0), ("size", True),
    ("digest", None), ("digest", "sha256:" + "z" * 64),
    ("browser_download_url", "https://evil.example/uv.tar.gz"),
])
def test_reject_incomplete_or_changed_release_provenance(field, value):
    data = json.loads(metadata())
    data["assets"][0][field] = value
    with pytest.raises(ValueError):
        uv.release_asset("0.9.11", json.dumps(data).encode())


def test_exact_version_and_unique_asset_required():
    with pytest.raises(ValueError, match="exact"):
        uv.release_asset("latest", metadata())
    with pytest.raises(ValueError, match="tag"):
        uv.release_asset("0.9.5", metadata())
    data = json.loads(metadata())
    data["assets"] *= 2
    with pytest.raises(ValueError, match="exactly one"):
        uv.release_asset("0.9.11", json.dumps(data).encode())


def test_registered_archive_and_metadata_are_revalidated(tmp_path):
    manifest, blob = make_cache(tmp_path)
    assert uv.registered_assets(tmp_path, manifest)[uv.asset_path("0.9.11")][0] == blob
    blob.write_bytes(b"x" * blob.stat().st_size)
    with pytest.raises(ValueError, match="SHA256"):
        uv.registered_assets(tmp_path, manifest)


def test_manifest_cannot_change_original_size_or_digest(tmp_path):
    manifest, _ = make_cache(tmp_path)
    data = json.loads(manifest.read_text())
    data["assets"][0]["size"] += 1
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="metadata"):
        uv.registered_assets(tmp_path, manifest)
    data["assets"][0]["release_metadata_sha256"] = "../../outside"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="digest"):
        uv.registered_assets(tmp_path, manifest)


def test_prepare_uses_fresh_original_index_and_verified_downloader(tmp_path, monkeypatch):
    calls = []
    raw = metadata()

    def get(url, headers, limit):
        calls.append(url)
        assert headers["Accept"] == "application/vnd.github+json"
        return 200, {}, raw

    def fetch(cache, entry, url, headers, workers, chunk):
        assert entry == uv.release_asset("0.9.11", raw)
        assert url == entry["url"] and headers == {} and workers == 16
        assert chunk == 256 * 1024
        calls.append("verified_download")

    monkeypatch.setattr(uv.ranges, "get", get)
    monkeypatch.setattr(uv.ranges, "fetch_blob", fetch)
    manifest = tmp_path / "plan.json"
    uv.prepare(tmp_path / "cache", manifest, ["0.9.11"])
    assert calls == ["https://api.github.com/repos/astral-sh/uv/releases/tags/0.9.11", "verified_download"]
    with pytest.raises(ValueError, match="overwritten"):
        uv.prepare(tmp_path / "cache", manifest, ["0.9.11"])


@pytest.fixture
def server(tmp_path):
    manifest, blob = make_cache(tmp_path)
    server = uv.ThreadingHTTPServer(("127.0.0.1", 0), uv.Handler)
    server.assets = uv.registered_assets(tmp_path, manifest)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, blob
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, path, method="GET", headers=None):
    connection = http.client.HTTPConnection(*server.server_address, timeout=5)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_http_exact_archive_head_and_resume(server):
    server, blob = server
    path = uv.asset_path("0.9.11")
    assert request(server, path)[2] == blob.read_bytes()
    status, headers, body = request(server, path, method="HEAD")
    assert status == 200 and body == b"" and int(headers["Content-Length"]) == blob.stat().st_size
    status, headers, body = request(server, path, headers={"Range": "bytes=3-8"})
    assert status == 206 and body == blob.read_bytes()[3:9]
    assert headers["Content-Range"] == f"bytes 3-8/{blob.stat().st_size}"
    assert request(server, path, headers={"Range": "bytes=999-"})[0] == 416


def test_unknown_versions_keep_original_github_source(server):
    server, _ = server
    path = uv.asset_path("0.9.99")
    status, headers, body = request(server, path)
    assert status == 302 and headers["Location"] == "https://github.com" + path and body == b""
    for bad in ["/private", "//evil.example/asset", "/astral-sh/uv/releases/download/../../private", uv.asset_path(".."), path + "?token=private"]:
        assert request(server, bad)[0] == 403


def test_http_corruption_fails_closed_after_server_start(server):
    server, blob = server
    blob.write_bytes(b"x" * blob.stat().st_size)
    status, _, body = request(server, uv.asset_path("0.9.11"))
    assert status == 502 and b"original uv archive" not in body
