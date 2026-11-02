#!/usr/bin/env python3
"""Update pinned version tags; restore files if fetching or vendoring fails."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FAKE_HASH = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
REV = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"sha256-[A-Za-z0-9+/]{43}=")


def latest_tag():
    # Upstream publishes version tags before creating GitHub Release entries.
    # Inspect all refs, sort numerically, and use peeled commits for annotated tags.
    refs = run("git", "ls-remote", "--tags", "https://github.com/yetone/magpie.git", "refs/tags/v*").stdout
    tags, commits = {}, {}
    for line in refs.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        sha, ref = fields
        match = re.fullmatch(r"refs/tags/v(" + VERSION.pattern + r")(\^\{\})?", ref)
        if not match:
            continue
        if not REV.fullmatch(sha):
            raise ValueError("invalid version tag revision")
        target = commits if match[2] else tags
        target[match[1]] = sha
    if not tags:
        raise ValueError("no vX.Y.Z version tags found")
    version = max(tags, key=lambda v: tuple(map(int, v.split("."))))
    return version, commits.get(version, tags[version])


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
    # Public upstream fetches and builds do not need workflow credentials.
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
        version, rev = latest_tag()
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
    parser.add_argument("--refresh", action="store_true", help="recompute hashes even if the version is unchanged")
    args = parser.parse_args()
    try:
        update(args.update_nixpkgs, args.refresh)
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
