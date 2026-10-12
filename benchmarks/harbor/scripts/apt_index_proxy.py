"""Accelerate original APT by-hash indexes without changing repositories.

Mutable release metadata and package downloads are forwarded without caching.
Only /by-hash/SHA256/<digest> objects are cached, after exact range, size and
whole-object SHA256 validation. APT still verifies signed release metadata and
the current index/package checksums. Bind only to a local Docker bridge.
"""

import argparse
from datetime import datetime, timezone
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


spec = importlib.util.spec_from_file_location(
    "verified_range_cache", Path(__file__).with_name("cache_image.py"),
)
ranges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ranges)

HOSTS = frozenset({
    "deb.debian.org", "security.debian.org", "archive.debian.org",
    "archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com",
    "old-releases.ubuntu.com",
})
BY_HASH = re.compile(r"/by-hash/SHA256/([0-9a-f]{64})$")
MAX_INDEX_BYTES = 128 * 1024 * 1024
REQUEST_HEADERS = {"if-modified-since", "if-none-match", "range", "user-agent"}
RESPONSE_HEADERS = {
    "content-type", "content-length", "content-range", "last-modified",
    "etag", "cache-control", "expires", "accept-ranges",
}


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in HOSTS
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 80, 443} or parsed.query or parsed.fragment):
        raise ValueError("Only original public APT origins without credentials are allowed")
    return parsed


class AptRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        validate_url(url)
        if urlsplit(request.full_url).scheme == "https" and urlsplit(url).scheme != "https":
            raise ValueError("HTTPS redirects cannot downgrade transport")
        return super().redirect_request(request, response, code, message, headers, url)


def open_origin(url, headers=None, method="GET"):
    validate_url(url)
    request = Request(url, headers={"Accept-Encoding": "identity", **(headers or {})}, method=method)
    return build_opener(ProxyHandler({}), AptRedirect()).open(request, timeout=30)


def public_get(url, headers=None, limit=1024 * 1024):
    for attempt in range(3):
        try:
            with open_origin(url, headers) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("Response exceeds requested range size")
                return response.status, dict(response.headers.items()), data
        except (URLError, OSError, TimeoutError, IncompleteRead) as error:
            if attempt == 2:
                raise RuntimeError(f"APT origin request failed: {type(error).__name__}") from None
            time.sleep(attempt + 1)


# Reuse the image utility's tested exact-range and whole-object verification.
ranges.get = lambda url, headers=None, limit=1024 * 1024: public_get(url, headers, limit)


class IndexCache:
    def __init__(self, root, workers=8, chunk_size=256 * 1024):
        if not 1 <= workers <= 16 or not 1024 <= chunk_size <= 1024 * 1024:
            raise ValueError("Invalid range worker count or chunk size")
        self.root = Path(root)
        self.workers, self.chunk_size = workers, chunk_size
        self.guard = threading.Lock()
        self.locks = {}

    def fetch(self, url):
        parsed = validate_url(url)
        match = BY_HASH.search(parsed.path)
        if not match:
            raise ValueError("Mutable URLs must not enter the index cache")
        digest = match.group(1)
        with self.guard:
            lock = self.locks.setdefault(digest, threading.Lock())
        with lock:
            path = self.root / "blobs/sha256" / digest
            if path.exists():
                size = path.stat().st_size
                if not 0 < size <= MAX_INDEX_BYTES:
                    raise ValueError("Cached index exceeds supported size")
                ranges.verify(path, {"digest": "sha256:" + digest, "size": size})
                return path, True
            status, headers, data = public_get(url, {"Range": "bytes=0-0"}, 1)
            headers = {key.lower(): value for key, value in headers.items()}
            content_range = re.fullmatch(r"bytes 0-0/(\d+)", headers.get("content-range", ""))
            if status != 206 or data == b"" or len(data) != 1 or not content_range:
                raise ValueError("Origin must return the exact size probe range")
            size = int(content_range.group(1))
            if not 0 < size <= MAX_INDEX_BYTES:
                raise ValueError("Index exceeds supported size")
            event(kind="download_start", host=parsed.hostname, sha256=digest, size=size)
            path = ranges.fetch_blob(
                self.root, {"digest": "sha256:" + digest, "size": size}, url, {},
                workers=self.workers, chunk_size=self.chunk_size,
            )
            return path, False


def byte_range(header, size):
    if header is None:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d+)-(\d*)", header)
    if not match:
        raise ValueError("Unsupported byte range")
    start = int(match.group(1))
    end = min(int(match.group(2)), size - 1) if match.group(2) else size - 1
    if start >= size or end < start:
        raise ValueError("Unsatisfiable byte range")
    return start, end, 206


def event(**fields):
    print(json.dumps({"time": datetime.now(timezone.utc).isoformat(), **fields}), flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass  # Do not publish arbitrary request URLs or headers.

    def do_GET(self):
        self.respond(head=False)

    def do_HEAD(self):
        self.respond(head=True)

    def respond(self, head):
        self.close_connection = True
        self.response_started = False
        try:
            parsed = validate_url(self.path)
        except ValueError:
            self.send_error(403, "Unsupported APT origin")
            return
        try:
            if BY_HASH.search(parsed.path):
                path, hit = self.server.cache.fetch(self.path)
                size = path.stat().st_size
                try:
                    start, end, status = byte_range(self.headers.get("Range"), size)
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return
                self.send_response(status)
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Connection", "close")
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                if not head:
                    with path.open("rb") as stream:
                        stream.seek(start)
                        left = end - start + 1
                        while left:
                            block = stream.read(min(left, 64 * 1024))
                            self.wfile.write(block)
                            left -= len(block)
                event(kind="index", host=parsed.hostname, sha256=path.name, size=size, cache_hit=hit)
            else:
                self.forward(head)
        except (BrokenPipeError, ConnectionResetError):
            event(kind="client_disconnected", host=parsed.hostname)
        except Exception as error:
            event(kind="error", host=parsed.hostname, error_type=type(error).__name__)
            if not self.response_started:
                self.send_error(502, "APT origin transfer or integrity validation failed")

    def end_headers(self):
        self.response_started = True
        super().end_headers()

    def forward(self, head):
        headers = {k: v for k, v in self.headers.items() if k.lower() in REQUEST_HEADERS}
        try:
            response = open_origin(self.path, headers, "HEAD" if head else "GET")
        except HTTPError as error:
            response = error
        with response:
            self.send_response(response.status)
            for key, value in response.headers.items():
                if key.lower() in RESPONSE_HEADERS:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            if not head:
                while block := response.read(64 * 1024):
                    self.wfile.write(block)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", required=True, help="Local Docker bridge address, not a public interface")
    parser.add_argument("--port", type=int, default=18742)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.bind in {"0.0.0.0", "::", ""}:
        parser.error("Binding all interfaces is not supported")
    cache = IndexCache(args.cache, args.workers)
    cache.root.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (cache.root / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        server = ThreadingHTTPServer((args.bind, args.port), Handler)
        server.cache = cache
        event(kind="ready", bind=args.bind, port=args.port, workers=args.workers)
        server.serve_forever()


if __name__ == "__main__":
    main()
