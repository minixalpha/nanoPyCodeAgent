"""Cache original uv release archives using GitHub's filename, size, and SHA256.

The official installer remains unchanged. Its supported
UV_INSTALLER_GITHUB_BASE_URL setting can point to the loopback server. Uncached
release paths redirect to the original HTTPS GitHub URL. No TLS interception,
general proxy environment variables, or alternate packages are involved.
"""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import re


spec = importlib.util.spec_from_file_location(
    "uv_verified_ranges", Path(__file__).with_name("cache_image.py"),
)
ranges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ranges)

ASSET = "uv-x86_64-unknown-linux-gnu.tar.gz"
VERSION = re.compile(r"\d+\.\d+\.\d+")
RELEASE_PATH = re.compile(
    r"/astral-sh/uv/releases/download/([0-9A-Za-z][0-9A-Za-z._+-]*)/"
    r"(uv-[0-9A-Za-z._-]+\.(?:tar\.gz|zip)(?:\.sha256)?)",
)


def asset_path(version, name=ASSET):
    return f"/astral-sh/uv/releases/download/{version}/{name}"


def release_asset(version, raw):
    if not VERSION.fullmatch(version):
        raise ValueError("Expected an exact stable uv version")
    release = json.loads(raw)
    if release.get("tag_name") != version:
        raise ValueError("Release tag differs from the requested version")
    matches = [asset for asset in release["assets"] if asset["name"] == ASSET]
    if len(matches) != 1:
        raise ValueError("Expected exactly one original Linux archive")
    asset = matches[0]
    url = "https://github.com" + asset_path(version)
    if (asset.get("browser_download_url") != url
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or "")
            or type(asset.get("size")) is not int or not 0 < asset["size"] <= 128 * 1024 * 1024):
        raise ValueError("Release archive lacks valid original provenance")
    return dict(version=version, filename=ASSET, url=url,
                digest=asset["digest"], size=asset["size"], asset_id=asset["id"],
                release_metadata_sha256=hashlib.sha256(raw).hexdigest())


def prepare(cache, manifest, versions, workers=16):
    if manifest.exists():
        raise ValueError("A registered release manifest cannot be overwritten")
    if not versions or len(versions) != len(set(versions)):
        raise ValueError("Specify distinct exact uv versions")
    if any(not VERSION.fullmatch(version) for version in versions):
        raise ValueError("Expected exact stable uv versions")
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / ".prepare.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        entries = []
        for version in versions:
            url = f"https://api.github.com/repos/astral-sh/uv/releases/tags/{version}"
            status, _, raw = ranges.get(url, {
                "User-Agent": "nanoPyCodeAgent-verified-cache",
                "Accept": "application/vnd.github+json",
            }, 4 * 1024 * 1024)
            if status != 200:
                raise ValueError("Original release metadata request failed")
            entry = release_asset(version, raw)
            metadata = cache / "metadata" / (entry["release_metadata_sha256"] + ".json")
            metadata.parent.mkdir(exist_ok=True)
            metadata.write_bytes(raw)
            ranges.fetch_blob(cache, entry, entry["url"], {}, workers, 256 * 1024)
            entries.append(entry)
            print(json.dumps({"verified_version": version, "size": entry["size"],
                              "digest": entry["digest"]}), flush=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "metadata_source": "Original public GitHub release API, fetched before this registration",
            "assets": entries,
        }, indent=2) + "\n")


def registered_assets(cache, manifest):
    entries = json.loads(manifest.read_text())["assets"]
    assets = {}
    if not entries:
        raise ValueError("Release manifest is empty")
    for entry in entries:
        if not re.fullmatch(r"[0-9a-f]{64}", entry.get("release_metadata_sha256", "")):
            raise ValueError("Invalid release metadata digest")
        metadata = cache / "metadata" / (entry["release_metadata_sha256"] + ".json")
        raw = metadata.read_bytes()
        if release_asset(entry["version"], raw) != entry:
            raise ValueError("Manifest differs from its original release metadata")
        path = asset_path(entry["version"], entry["filename"])
        if path in assets:
            raise ValueError("Duplicate registered release")
        blob = ranges.blob_path(cache, entry)
        ranges.verify(blob, entry)
        assets[path] = (blob, entry)
    return assets


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.respond(False)

    def do_HEAD(self):
        self.respond(True)

    def respond(self, head):
        self.close_connection = True
        if not RELEASE_PATH.fullmatch(self.path):
            self.send_error(403, "Only original uv release assets are supported")
            return
        cached = self.server.assets.get(self.path)
        if cached is None:
            self.send_response(302)
            self.send_header("Location", "https://github.com" + self.path)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            return
        blob, entry = cached
        try:
            ranges.verify(blob, entry)
        except (OSError, ValueError):
            self.send_error(502, "Registered uv archive failed integrity validation")
            return
        start, end = 0, entry["size"] - 1
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", requested)
            if match:
                start = int(match.group(1))
                end = min(int(match.group(2)), end) if match.group(2) else end
            if not match or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{entry['size']}")
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                return
        self.send_response(206 if requested else 200)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Connection", "close")
        if requested:
            self.send_header("Content-Range", f"bytes {start}-{end}/{entry['size']}")
        self.end_headers()
        if not head:
            try:
                with blob.open("rb") as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = stream.read(min(remaining, 64 * 1024))
                        if not block:
                            raise OSError("Verified archive changed during transfer")
                        self.wfile.write(block)
                        remaining -= len(block)
            except OSError:
                return  # Close a partial transfer; never fabricate successful bytes.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "serve"])
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--version", action="append", default=[])
    parser.add_argument("--bind", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--port", type=int, default=18743)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.cache, args.manifest, args.version)
    else:
        assets = registered_assets(args.cache, args.manifest)
        server = ThreadingHTTPServer((args.bind, args.port), Handler)
        server.assets = assets
        print(json.dumps({"ready": True, "registered_archives": len(assets)}), flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
