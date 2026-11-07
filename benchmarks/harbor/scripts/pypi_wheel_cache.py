"""Serve the original PyPI index with hash-verified, ranged wheel downloads.

Point uv's default index at this loopback service. Project metadata is always
fetched from PyPI; versions, requirements, yanks, hashes and extra indexes are
preserved. Only wheel URLs are routed through the cache. Every wheel request
rechecks the current PyPI release metadata before serving any cached bytes.
"""

import argparse
from datetime import datetime, timezone
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import quote, unquote, urlsplit


spec = importlib.util.spec_from_file_location(
    "pypi_verified_ranges", Path(__file__).with_name("cache_image.py"),
)
ranges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ranges)
PROJECT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
WHEEL = re.compile(r"[A-Za-z0-9_.+!-]+\.whl")
DIGEST = re.compile(r"[a-f0-9]{64}")
AUDIT_LOG = None


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def event(**values):
    line = json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                       "instance": os.environ.get("HOSTNAME", "local"), **values})
    if AUDIT_LOG is not None:
        with AUDIT_LOG.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(line + "\n")
            stream.flush()
    print(line, flush=True)


def public_json(url, *, accept="application/json"):
    status, _, body = ranges.get(url, {"Accept": accept}, 32 * 1024 * 1024)
    if status != 200:
        raise ValueError("PyPI metadata request did not succeed")
    return json.loads(body)


def official_wheel_url(url, filename):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "files.pythonhosted.org"
            or parsed.query or parsed.fragment
            or unquote(parsed.path.rsplit("/", 1)[-1]) != filename):
        raise ValueError("Wheel must retain its original PyPI file URL")
    return url


class WheelCache:
    def __init__(self, root, *, workers=16, downloads=2):
        self.root = Path(root)
        self.workers = workers
        self.slots = threading.BoundedSemaphore(downloads)
        (self.root / "locks").mkdir(parents=True, exist_ok=True)

    def index(self, project):
        if not PROJECT.fullmatch(project):
            raise ValueError("Invalid normalized project name")
        data = public_json(
            f"https://pypi.org/simple/{project}/",
            accept="application/vnd.pypi.simple.v1+json",
        )
        for file in data["files"]:
            name = file["filename"]
            if not WHEEL.fullmatch(name):
                continue  # Source distributions retain their original URLs.
            digest = file["hashes"]["sha256"]
            if not DIGEST.fullmatch(digest):
                raise ValueError("PyPI wheel lacks a SHA256 digest")
            official_wheel_url(file["url"], name)
            file["url"] = f"/files/{project}/{digest}/{quote(name, safe='')}"
        return data

    def release_file(self, project, digest, filename):
        if (not PROJECT.fullmatch(project) or not DIGEST.fullmatch(digest)
                or not WHEEL.fullmatch(filename)):
            raise ValueError("Invalid wheel request")
        parts = filename.split("-")
        if len(parts) < 5 or canonical(parts[0]) != project:
            raise ValueError("Wheel project differs from its index")
        version = parts[1]
        data = public_json(f"https://pypi.org/pypi/{project}/{quote(version, safe='')}/json")
        file = next((f for f in data["urls"] if f["filename"] == filename), None)
        if (file is None or file["digests"]["sha256"] != digest
                or type(file["size"]) is not int or file["size"] <= 0):
            raise ValueError("Wheel no longer matches current PyPI metadata")
        official_wheel_url(file["url"], filename)
        event(kind="release_metadata", project=project, version=version,
              filename=filename, size=file["size"], sha256=digest,
              source_url=file["url"])
        return file

    def wheel(self, file):
        digest = file["digests"]["sha256"]
        descriptor = {"digest": "sha256:" + digest, "size": file["size"]}
        # A host bind mount is shared by separate task-sidecar processes too.
        # Serialize publication across processes, not merely HTTP threads.
        with (self.root / "locks" / digest).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            cached = ranges.blob_path(self.root, descriptor).exists()
            with self.slots:
                path = ranges.fetch_blob(
                    self.root, descriptor, file["url"], {}, workers=self.workers,
                    chunk_size=4 * 1024 * 1024,
                )
            event(kind="wheel", filename=file["filename"], size=file["size"],
                  sha256=digest, cache_hit=cached)
            return path


def byte_range(header, size):
    if header is None:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()):
        raise ValueError("Unsupported byte range")
    first, last = match.groups()
    if first:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    else:
        start, end = max(0, size - int(last)), size - 1
    if start >= size or start > end:
        raise ValueError("Unsatisfiable byte range")
    return start, end, 206


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond(False)

    def do_HEAD(self):
        self.respond(True)

    def headers_for(self, status, size, content_type, **headers):
        self.send_response(status)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Type", content_type)
        self.send_header("Connection", "close")
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), str(value))
        self.end_headers()
        self.response_started = True

    def respond(self, head):
        self.close_connection = True
        self.response_started = False
        path = urlsplit(self.path)
        if path.query or path.fragment:
            self.send_error(400, "Unexpected query")
            return
        try:
            if path.path.startswith("/astral-sh/") and hasattr(self.server, "releases"):
                self.server.releases.Handler.respond(self, head)
                return
            if path.path == "/health":
                self.headers_for(200, 0, "text/plain")
                return
            index = re.fullmatch(r"/simple/([a-z0-9-]+)/?", path.path)
            if index:
                body = json.dumps(self.server.cache.index(index[1])).encode()
                self.headers_for(200, len(body), "application/vnd.pypi.simple.v1+json", Cache_Control="no-cache")
                if not head:
                    self.wfile.write(body)
                return
            match = re.fullmatch(r"/files/([^/]+)/([^/]+)/([^/]+)", path.path)
            if not match:
                self.send_error(404, "Unknown cache endpoint")
                return
            project, digest, filename = (unquote(value) for value in match.groups())
            metadata = filename.endswith(".whl.metadata")
            if metadata:
                filename = filename.removesuffix(".metadata")
            file = self.server.cache.release_file(project, digest, filename)
            if metadata:
                # Preserve the original PEP 658 bytes and advertised hashes.
                # Metadata is forwarded fresh, never restored from this cache.
                status, _, body = ranges.get(file["url"] + ".metadata", limit=4 * 1024 * 1024)
                if status != 200:
                    raise ValueError("Original wheel metadata is unavailable")
                self.headers_for(200, len(body), "application/octet-stream", Cache_Control="no-cache")
                if not head:
                    self.wfile.write(body)
                return
            try:
                start, end, status = byte_range(self.headers.get("Range"), file["size"])
            except ValueError:
                self.headers_for(416, 0, "application/octet-stream", Content_Range=f"bytes */{file['size']}")
                return
            blob = None if head else self.server.cache.wheel(file)
            headers = {"Accept_Ranges": "bytes", "ETag": '"' + digest + '"'}
            if status == 206:
                headers["Content_Range"] = f"bytes {start}-{end}/{file['size']}"
            self.headers_for(status, end - start + 1, "application/octet-stream", **headers)
            if not head:
                with blob.open("rb") as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = stream.read(min(remaining, 64 * 1024))
                        if not block:
                            return  # Incomplete transfers cannot fabricate valid wheel bytes.
                        self.wfile.write(block)
                        remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            event(kind="error", error_type=type(error).__name__)
            if not self.response_started:
                self.send_error(502, "Original PyPI metadata or wheel validation failed")


def configure_releases(server, cache, manifest):
    """Use the reviewed original-release handler on the same loopback listener."""
    spec = importlib.util.spec_from_file_location(
        "dependency_release_cache", Path(__file__).with_name("uv_release_cache.py"),
    )
    releases = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(releases)
    server.assets = releases.registered_assets(cache, manifest)
    server.releases = releases
    server.release_event = event


def main():
    global AUDIT_LOG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18744)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--downloads", type=int, default=2)
    parser.add_argument("--release-cache", type=Path)
    parser.add_argument("--release-manifest", type=Path)
    parser.add_argument("--audit-log", type=Path,
                        help="Append public metadata and verified cache events for the run")
    args = parser.parse_args()
    if not 1 <= args.workers <= 32 or not 1 <= args.downloads <= 4:
        parser.error("Use 1-32 workers and 1-4 concurrent wheel downloads")
    if bool(args.release_cache) != bool(args.release_manifest):
        parser.error("Both release cache and manifest are required")
    AUDIT_LOG = args.audit_log
    if AUDIT_LOG is not None:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.cache = WheelCache(args.cache, workers=args.workers, downloads=args.downloads)
    if args.release_cache:
        configure_releases(server, args.release_cache, args.release_manifest)
    event(kind="ready", bind=args.bind, port=args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
