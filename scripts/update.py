#!/usr/bin/env python3
"""Update pinned release sources; restore files if fetching or vendoring fails."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com/repos/yetone/magpie"
FAKE_HASH = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
REV = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"sha256-[A-Za-z0-9+/]{43}=")


def github(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "magpie-nix-updater"}
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(API + path, headers=headers), timeout=60) as response:
        return json.load(response)


def latest_release():
    release = github("/releases/latest")
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v" + VERSION.pattern, tag):
        raise ValueError("latest release is not a stable vX.Y.Z release")
    obj = github("/git/ref/tags/" + tag)["object"]
    # Annotated tags point at tag objects; pin the actual commit instead.
    for _ in range(5):
        if not REV.fullmatch(obj["sha"]):
            raise ValueError("invalid release revision")
        if obj["type"] == "commit":
            return tag[1:], obj["sha"]
        if obj["type"] != "tag":
            break
        obj = github("/git/tags/" + obj["sha"])["object"]
    raise ValueError("release tag did not resolve to a commit")


def validate_source(source):
    if set(source) != {"version", "rev", "hash", "vendorHash"}:
        raise ValueError("unexpected source fields")
    for key, pattern in (("version", VERSION), ("rev", REV), ("hash", HASH), ("vendorHash", HASH)):
        if not isinstance(source[key], str) or not pattern.fullmatch(source[key]):
            raise ValueError(f"invalid source {key}")


def check_release(current, version, rev):
    if not VERSION.fullmatch(version) or not REV.fullmatch(rev):
        raise ValueError("invalid release version or revision")
    if tuple(map(int, version.split("."))) < tuple(map(int, current["version"].split("."))):
        raise ValueError("refusing an automatic downgrade")
    if version == current["version"] and rev != current["rev"]:
        raise ValueError("release tag moved; review the upstream change manually")


def run(*args, check=True):
    # Only API metadata requests need a token. Do not pass it into build tools.
    env = {k: v for k, v in os.environ.items() if k not in {"GH_TOKEN", "GITHUB_TOKEN"}}
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result


def write_source(source):
    validate_source(source)
    (ROOT / "sources.json").write_text(json.dumps(source, indent=2) + "\n")


def vendor_hash():
    system = run("nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem").stdout.strip()
    if system != "x86_64-linux":
        raise ValueError("update on x86_64-linux")
    command = (
        "nix", "build", f".#packages.{system}.magpie.goModules", "--no-link",
        "--no-write-lock-file", "--print-build-logs", "--log-format", "raw",
    )
    result = run(*command, check=False)
    found = set(re.findall(r"got:\s+(sha256-[A-Za-z0-9+/]{43}=)", result.stdout + result.stderr))
    if result.returncode == 0 or len(found) != 1:
        raise RuntimeError("could not determine vendorHash:\n" + result.stdout + result.stderr)
    return found.pop(), command


def update(update_nixpkgs=False, refresh=False):
    paths = [ROOT / "sources.json", ROOT / "flake.lock"]
    before = {p: p.read_bytes() for p in paths}
    try:
        current = json.loads(before[paths[0]])
        validate_source(current)
        version, rev = latest_release()
        check_release(current, version, rev)
        if update_nixpkgs:
            run("nix", "flake", "update", "nixpkgs")
        changed = (version, rev) != (current["version"], current["rev"])
        if changed or refresh or paths[1].read_bytes() != before[paths[1]]:
            url = f"https://github.com/yetone/magpie/archive/{rev}.tar.gz"
            fetched = json.loads(run("nix", "store", "prefetch-file", "--unpack", "--json", url).stdout)
            source = dict(version=version, rev=rev, hash=fetched["hash"], vendorHash=FAKE_HASH)
            write_source(source)
            source["vendorHash"], command = vendor_hash()
            write_source(source)
            # Verify the discovered hash instead of trusting parsed error output alone.
            run(*command)
        changed = any(p.read_bytes() != before[p] for p in paths)
        print(f"Magpie {version}: {'updated' if changed else 'already current'}")
        return changed
    except BaseException:
        for path, content in before.items():
            path.write_bytes(content)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-nixpkgs", action="store_true", help="also advance the nixpkgs lock")
    parser.add_argument("--refresh", action="store_true", help="recompute hashes even if the release is unchanged")
    args = parser.parse_args()
    try:
        update(args.update_nixpkgs, args.refresh)
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
