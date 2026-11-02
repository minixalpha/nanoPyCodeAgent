"""Original-index preservation and fail-closed wheel cache contracts."""

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


spec = importlib.util.spec_from_file_location(
    "pypi_cache_test", Path(__file__).parents[1] / "scripts/pypi_wheel_cache.py",
)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


@pytest.fixture
def origin(tmp_path, monkeypatch):
    content = b"original wheel bytes"
    metadata = b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n"
    digest = hashlib.sha256(content).hexdigest()
    name = "demo-1.0-py3-none-any.whl"
    url = "https://files.pythonhosted.org/packages/original/" + name
    file = {"filename": name, "size": len(content), "url": url,
            "digests": {"sha256": digest}}
    release = {"urls": [file]}
    index = {"meta": {"api-version": "1.4"}, "name": "demo", "files": [{
        "filename": name, "size": len(content), "url": url,
        "hashes": {"sha256": digest}, "requires-python": ">=3.10", "yanked": "test yank reason",
        "core-metadata": {"sha256": hashlib.sha256(metadata).hexdigest()},
    }, {"filename": "demo-1.0.tar.gz", "url": "https://files.pythonhosted.org/demo-1.0.tar.gz"}]}
    requests = []

    def public_json(url, **kwargs):
        requests.append(url)
        if url == "https://pypi.org/simple/demo/":
            return copy.deepcopy(index)
        assert url == "https://pypi.org/pypi/demo/1.0/json"
        return copy.deepcopy(release)

    def get(request_url, headers=None, limit=None):
        requests.append(request_url)
        if request_url == url + ".metadata":
            return 200, {}, metadata
        assert request_url == url
        assert headers["Range"] == f"bytes=0-{len(content) - 1}"
        return 206, {"Content-Range": f"bytes 0-{len(content) - 1}/{len(content)}"}, content

    monkeypatch.setattr(proxy, "public_json", public_json)
    monkeypatch.setattr(proxy.ranges, "get", get)
    cache = proxy.WheelCache(tmp_path / "cache")
    return cache, file, release, index, content, metadata, requests


def test_index_changes_only_wheel_urls_and_refreshes_origin(origin):
    cache, file, _, index, _, _, requests = origin
    actual = cache.index("demo")
    expected = copy.deepcopy(index)
    expected["files"][0]["url"] = f"/files/demo/{file['digests']['sha256']}/{file['filename']}"
    assert actual == expected
    index["files"][0]["yanked"] = False
    assert cache.index("demo")["files"][0]["yanked"] is False
    assert requests.count("https://pypi.org/simple/demo/") == 2


@pytest.mark.parametrize("change", ["filename", "size", "sha256", "url", "missing"])
def test_cached_wheel_is_rejected_when_current_metadata_changes(origin, change):
    cache, file, release, _, content, _, requests = origin
    name, digest = file["filename"], file["digests"]["sha256"]
    assert cache.wheel(cache.release_file("demo", digest, name)).read_bytes() == content
    if change == "missing":
        release["urls"] = []
    elif change == "sha256":
        file["digests"]["sha256"] = "0" * 64
    elif change == "size":
        file["size"] += 1
    elif change == "url":
        file["url"] = "https://example.com/" + name
    else:
        file["filename"] = "demo-1.1-py3-none-any.whl"
    with pytest.raises(ValueError):
        cache.wheel(cache.release_file("demo", digest, name))
    assert requests.count("https://pypi.org/pypi/demo/1.0/json") == 2


def test_corrupt_cached_bytes_fail_closed_before_serving(origin):
    cache, file, _, _, content, _, _ = origin
    path = cache.wheel(file)
    path.write_bytes(b"x" * len(content))
    with pytest.raises(ValueError, match="SHA256"):
        cache.wheel(cache.release_file("demo", file["digests"]["sha256"], file["filename"]))


def test_audit_retains_current_origin_identity_and_verified_cache_hit(origin, tmp_path, monkeypatch):
    cache, file, _, _, _, _, _ = origin
    log = tmp_path / "audit.jsonl"
    monkeypatch.setattr(proxy, "AUDIT_LOG", log)
    for _ in range(2):
        cache.wheel(cache.release_file("demo", file["digests"]["sha256"], file["filename"]))
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [event["kind"] for event in events] == ["release_metadata", "wheel"] * 2
    assert events[0]["source_url"] == file["url"]
    assert all(event["sha256"] == file["digests"]["sha256"] for event in events)
    assert [events[i]["cache_hit"] for i in (1, 3)] == [False, True]


@pytest.mark.parametrize("project,digest,name", [
    ("../demo", "a" * 64, "demo-1.0-py3-none-any.whl"),
    ("demo", "../escape", "demo-1.0-py3-none-any.whl"),
    ("demo", "a" * 64, "../demo-1.0-py3-none-any.whl"),
    ("other", "a" * 64, "demo-1.0-py3-none-any.whl"),
])
def test_request_paths_cannot_escape_or_change_the_project(origin, project, digest, name):
    cache, _, _, _, _, _, requests = origin
    with pytest.raises(ValueError):
        cache.release_file(project, digest, name)
    assert not requests


def test_separate_cache_instances_serialize_shared_blob_publication(origin, monkeypatch):
    cache, file, _, _, _, _, _ = origin
    other = proxy.WheelCache(cache.root)
    active = 0
    maximum = 0
    guard = threading.Lock()

    def fetch(*args, **kwargs):
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.03)
        with guard:
            active -= 1
        return cache.root / "placeholder"

    monkeypatch.setattr(proxy.ranges, "fetch_blob", fetch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda item: item.wheel(file), [cache, other]))
    assert maximum == 1


@pytest.fixture
def server(origin):
    cache = origin[0]
    server = ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
    server.cache = cache
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def wheel_url(server, origin):
    file = origin[1]
    return server + f"/files/demo/{file['digests']['sha256']}/{file['filename']}"


def test_http_index_head_and_range_deliver_original_bytes(server, origin):
    _, file, _, _, content, _, _ = origin
    with urlopen(server + "/simple/demo/") as response:
        assert json.load(response)["files"][0]["url"].endswith(file["filename"])
        assert response.headers["Cache-Control"] == "no-cache"
    url = wheel_url(server, origin)
    with urlopen(Request(url, method="HEAD")) as response:
        assert int(response.headers["Content-Length"]) == len(content)
        assert response.read() == b""
    for requested, expected in [("bytes=2-6", content[2:7]), ("bytes=-5", content[-5:])]:
        with urlopen(Request(url, headers={"Range": requested})) as response:
            assert response.status == 206
            assert response.read() == expected
    with pytest.raises(HTTPError) as error:
        urlopen(Request(url, headers={"Range": "bytes=999-"}))
    assert error.value.code == 416


def test_http_metadata_is_forwarded_fresh_and_keeps_original_bytes(server, origin):
    _, file, _, _, _, metadata, requests = origin
    for _ in range(2):
        with urlopen(wheel_url(server, origin) + ".metadata") as response:
            assert response.read() == metadata
    assert requests.count(file["url"] + ".metadata") == 2


def test_http_corrupt_cache_never_returns_successful_content(server, origin):
    cache, file, _, _, content, _, _ = origin
    cache.wheel(file).write_bytes(b"x" * len(content))
    with pytest.raises(HTTPError) as error:
        urlopen(wheel_url(server, origin))
    assert error.value.code == 502
