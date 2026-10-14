"""The APT transport cache must preserve original content and trust checks."""

import hashlib
import http.client
import importlib.util
import io
import multiprocessing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
from urllib.error import HTTPError

import pytest

spec = importlib.util.spec_from_file_location(
    "apt_index_proxy", Path(__file__).parents[1] / "scripts/apt_index_proxy.py",
)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


def fixture(payload):
    digest = hashlib.sha256(payload).hexdigest()
    return "http://deb.debian.org/debian/dists/bookworm/main/binary-amd64/by-hash/SHA256/" + digest


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/private", "http://deb.debian.org.evil.example/file",
    "http://user:secret@deb.debian.org/file", "file:///etc/passwd",
    "http://deb.debian.org:8080/file", "http://deb.debian.org/file?token=secret",
    "http://deb.debian.org/file#fragment",
])
def test_restrict_origins(url):
    with pytest.raises(ValueError):
        proxy.validate_url(url)


def test_mutable_metadata_and_debs_never_enter_cache(tmp_path):
    cache = proxy.IndexCache(tmp_path)
    for suffix in ["dists/bookworm/InRelease", "dists/bookworm/main/Packages.xz", "pool/main/p/package.deb"]:
        with pytest.raises(ValueError, match="Mutable"):
            cache.fetch("http://deb.debian.org/debian/" + suffix)
    assert not list(tmp_path.iterdir())


def fake_origin(payload, requests):
    def get(url, headers, limit):
        start, end = map(int, headers["Range"].removeprefix("bytes=").split("-"))
        requests.append((start, end))
        return 206, {"Content-Range": f"bytes {start}-{end}/{len(payload)}"}, payload[start:end + 1]
    return get


def test_shared_index_is_verified_and_downloaded_once(tmp_path, monkeypatch):
    payload = bytes(range(256)) * 20
    requests = []
    monkeypatch.setattr(proxy, "public_get", fake_origin(payload, requests))
    cache = proxy.IndexCache(tmp_path, workers=2, chunk_size=1024)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(cache.fetch, [fixture(payload)] * 2))
    assert sorted(hit for _, hit in results) == [False, True]
    assert len(requests) == 6  # Size probe plus five exact chunks.
    assert all(path.read_bytes() == payload for path, _ in results)


def test_corrupt_cached_index_is_never_served(tmp_path, monkeypatch):
    payload = b"trusted signed-index bytes"
    monkeypatch.setattr(proxy, "public_get", fake_origin(payload, []))
    cache = proxy.IndexCache(tmp_path)
    path, _ = cache.fetch(fixture(payload))
    path.write_bytes(b"x" * len(payload))
    with pytest.raises(ValueError, match="SHA256"):
        cache.fetch(fixture(payload))


def test_separate_proxy_processes_share_verified_cache(tmp_path, monkeypatch):
    context = multiprocessing.get_context("fork")
    start, results, calls = context.Event(), context.Queue(), context.Value("i", 0)
    payload = bytes(range(256)) * 20
    origin = fake_origin(payload, [])

    def get(*args):
        with calls.get_lock():
            calls.value += 1
        return origin(*args)

    monkeypatch.setattr(proxy, "public_get", get)

    def fetch():
        start.wait(5)
        path, hit = proxy.IndexCache(tmp_path, workers=2, chunk_size=1024).fetch(fixture(payload))
        results.put((path.read_bytes() == payload, hit))

    processes = [context.Process(target=fetch) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        start.set()
        assert sorted(results.get(timeout=10) for _ in processes) == [(True, False), (True, True)]
        for process in processes:
            process.join(5)
            assert process.exitcode == 0
        assert calls.value == 6
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)


def test_wrong_origin_content_is_never_committed(tmp_path, monkeypatch):
    payload = b"original content"
    monkeypatch.setattr(proxy, "public_get", fake_origin(b"modified content", []))
    cache = proxy.IndexCache(tmp_path)
    with pytest.raises(ValueError, match="SHA256"):
        cache.fetch(fixture(payload))
    digest = hashlib.sha256(payload).hexdigest()
    assert not (tmp_path / "blobs/sha256" / digest).exists()


@pytest.mark.parametrize("status,header,body", [
    (200, "bytes 0-0/10", b"x"), (206, "bytes 1-1/10", b"x"),
    (206, "bytes 0-0/10", b""), (206, "bytes 0-0/9999999999", b"x"),
])
def test_reject_invalid_size_probe(tmp_path, monkeypatch, status, header, body):
    monkeypatch.setattr(proxy, "public_get", lambda *_args: (status, {"Content-Range": header}, body))
    with pytest.raises(ValueError):
        proxy.IndexCache(tmp_path).fetch(fixture(b"original"))


def test_resumed_range_matches_original_file_bytes():
    assert proxy.byte_range(None, 10) == (0, 9, 200)
    assert proxy.byte_range("bytes=3-", 10) == (3, 9, 206)
    assert proxy.byte_range("bytes=3-99", 10) == (3, 9, 206)
    for bad in ["bytes=10-", "bytes=5-3", "bytes=-3", "bytes=0-1,3-4"]:
        with pytest.raises(ValueError):
            proxy.byte_range(bad, 10)


@pytest.fixture
def server(tmp_path):
    server = proxy.ThreadingHTTPServer(("127.0.0.1", 0), proxy.Handler)
    server.cache = proxy.IndexCache(tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, url, method="GET", headers=None):
    connection = http.client.HTTPConnection(*server.server_address, timeout=5)
    try:
        connection.request(method, url, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_http_serves_only_verified_content_and_correct_ranges(server, monkeypatch):
    payload = b"exact original index"
    monkeypatch.setattr(proxy, "public_get", fake_origin(payload, []))
    url = fixture(payload)
    assert request(server, url)[2] == payload
    status, headers, body = request(server, url, headers={"Range": "bytes=3-7"})
    assert status == 206 and body == payload[3:8]
    assert headers["Content-Range"] == f"bytes 3-7/{len(payload)}"
    status, headers, body = request(server, url, method="HEAD")
    assert status == 200 and body == b"" and int(headers["Content-Length"]) == len(payload)
    assert request(server, url, headers={"Range": "bytes=999-"})[0] == 416
    assert request(server, "http://127.0.0.1/private")[0] == 403


def test_http_rejects_origin_hash_mismatch(server, monkeypatch):
    monkeypatch.setattr(proxy, "public_get", fake_origin(b"tampered index", []))
    status, _, body = request(server, fixture(b"original index"))
    assert status == 502 and b"tampered index" not in body


def test_release_metadata_is_fetched_again_and_conditionals_preserved(server, monkeypatch):
    calls = []
    def origin(url, headers, method):
        calls.append((headers, method))
        if "If-Modified-Since" in headers:
            raise HTTPError(url, 304, "Not Modified", {"Content-Length": "0"}, io.BytesIO())
        body = b"signed release " + str(len(calls)).encode()
        response = io.BytesIO(body)
        response.status = 200
        response.headers = {"Content-Length": str(len(body))}
        return response
    monkeypatch.setattr(proxy, "open_origin", origin)
    url = "http://deb.debian.org/debian/dists/bookworm/InRelease"
    assert request(server, url)[2] == b"signed release 1"
    assert request(server, url)[2] == b"signed release 2"
    assert request(server, url, headers={"If-Modified-Since": "original timestamp", "Authorization": "private"})[0] == 304
    assert calls[-1] == ({"If-Modified-Since": "original timestamp"}, "GET")
