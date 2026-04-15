#!/usr/bin/env python3
"""Assert VERSION is a valid semver string (no manual duplication to check)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[.\-].+)?$")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version_path = root / "VERSION"
    if not version_path.is_file():
        print("VERSION file not found", file=sys.stderr)
        return 1

    version = version_path.read_text(encoding="utf-8").strip()
    if not version:
        print("VERSION file is empty", file=sys.stderr)
        return 1

    if not SEMVER_RE.match(version):
        print(
            f"VERSION '{version}' does not look like a valid semver string",
            file=sys.stderr,
        )
        return 1

    print(f"VERSION is valid: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
