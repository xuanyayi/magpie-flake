#!/usr/bin/env python3
"""Update the pinned Magpie Stable release and optionally nixpkgs."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STABLE_FEED = "https://usemagpie.ai/api/latest?channel=stable"
FAKE_HASH = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
REV = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"sha256-[A-Za-z0-9+/]{43}=")


def latest_stable():
    request = Request(STABLE_FEED, headers={"User-Agent": "magpie-flake-updater"})
    with urlopen(request, timeout=30) as response:
        release = json.load(response)
    if not isinstance(release, dict) or release.get("channel") != "stable":
        raise ValueError("upstream feed did not return a Stable release")
    version = release.get("version")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("invalid version from the upstream Stable feed")

    tag = f"refs/tags/v{version}"
    peeled = tag + "^{}"
    result = run("git", "ls-remote", "--exit-code", "--tags", "https://github.com/yetone/magpie.git", tag, peeled)
    refs = {ref: sha for sha, ref in (line.split("\t") for line in result.stdout.splitlines())}
    rev = refs.get(peeled, refs.get(tag, ""))
    if not REV.fullmatch(rev):
        raise ValueError(f"invalid revision for Stable tag v{version}")
    return version, rev


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


def update(update_nixpkgs=False, refresh=False, nixpkgs_only=False):
    paths = [ROOT / "sources.json", ROOT / "flake.lock"]
    before = {p: p.read_bytes() for p in paths}
    current = json.loads(before[paths[0]])
    validate_source(current)
    if nixpkgs_only:
        version, rev = current["version"], current["rev"]
    else:
        version, rev = latest_stable()
        check_release(current, version, rev)
    changed = (version, rev) != (current["version"], current["rev"])

    try:
        if update_nixpkgs or nixpkgs_only:
            run("nix", "flake", "update", "nixpkgs")
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
    nixpkgs = parser.add_mutually_exclusive_group()
    nixpkgs.add_argument("--update-nixpkgs", action="store_true", help="also advance the nixpkgs lock")
    nixpkgs.add_argument("--nixpkgs-only", action="store_true", help="advance nixpkgs using the currently pinned Magpie version")
    parser.add_argument("--refresh", action="store_true", help="recompute hashes even if the version is unchanged")
    args = parser.parse_args()
    try:
        update(args.update_nixpkgs, args.refresh, args.nixpkgs_only)
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
