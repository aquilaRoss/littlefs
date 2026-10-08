#!/usr/bin/env python3
"""Check that the package URL in zephyr/module.yml matches the merged littlefs.

Zephyr's `west spdx` copies this package URL into the SBOMs it generates, and
vulnerability scanners match on it, so a stale version silently misreports
which littlefs a Zephyr build contains.

lfs.h only carries the major and minor version, so the newest upstream release
tag merged into HEAD is the source of truth. This needs full history.

Usage:
    python3 zephyr/check_module_version.py
"""

import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM_URL = "https://github.com/littlefs-project/littlefs.git"
# Outside refs/tags so the fetched tags never leak into a push of this fork.
TAG_NAMESPACE = "refs/upstream-tags/"
PURL_PREFIX = "pkg:github/littlefs-project/littlefs@"
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def git(*args):
    return subprocess.run(["git", "-C", REPO_ROOT, *args], check=True,
                          capture_output=True, text=True).stdout


def read_purl_versions():
    """Return every version named by a littlefs package URL in module.yml."""
    with open(os.path.join(REPO_ROOT, "zephyr", "module.yml"), encoding="utf-8") as fh:
        text = fh.read()
    return re.findall(r"^\s*-\s*" + re.escape(PURL_PREFIX) + r"(\S+)\s*$",
                      text, re.MULTILINE)


def newest_merged_release():
    """Return the newest upstream release tag reachable from HEAD, or None."""
    git("fetch", "--quiet", "--no-tags", UPSTREAM_URL,
        "+refs/tags/v*:" + TAG_NAMESPACE + "v*")
    names = git("for-each-ref", "--merged", "HEAD",
                "--format=%(refname:lstrip=2)", TAG_NAMESPACE).split()
    releases = [n for n in names if RELEASE_TAG.match(n)]
    if not releases:
        return None
    return max(releases, key=lambda n: tuple(int(x) for x in RELEASE_TAG.match(n).groups()))


def main():
    purl_versions = read_purl_versions()
    if len(purl_versions) != 1:
        print("zephyr/module.yml must list exactly one '%s<tag>' entry, found %d"
              % (PURL_PREFIX, len(purl_versions)))
        return 1
    purl_version = purl_versions[0]

    merged = newest_merged_release()
    if merged is None:
        print("No littlefs release tag from %s is merged into HEAD; "
              "is this a shallow clone?" % UPSTREAM_URL)
        return 1

    if purl_version != merged:
        print("zephyr/module.yml names littlefs %s but the newest merged "
              "upstream release is %s" % (purl_version, merged))
        return 1

    print("zephyr/module.yml matches the newest merged upstream release (%s)" % merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
