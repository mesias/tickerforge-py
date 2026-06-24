#!/usr/bin/env python3
"""Copy canonical spec files from sibling tickerforge-spec repository to local spec directory."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    py_root = Path(__file__).resolve().parents[1]
    spec_source = py_root.parent / "tickerforge-spec" / "spec"
    spec_dest = py_root / "spec"

    if not spec_source.is_dir():
        print(f"Source spec directory not found: {spec_source}", file=sys.stderr)
        return 1

    print(f"Copying spec from {spec_source} to {spec_dest}...")
    try:
        if spec_dest.exists():
            shutil.rmtree(spec_dest)
        shutil.copytree(spec_source, spec_dest)
        print("Spec updated successfully.")
        return 0
    except Exception as e:
        print(f"Error copying spec: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
