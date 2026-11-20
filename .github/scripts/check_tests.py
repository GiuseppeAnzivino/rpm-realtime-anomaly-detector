"""Verify that every source module of a microservice has a matching test file.

Usage: python check_tests.py <service_dir>

Convention: src/<path>/<name>.py  ->  tests/<path>/test_<name>.py
__init__.py files are ignored. Additional test files with other names
are allowed and are executed by pytest as usual.
"""
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python check_tests.py <service_dir>")
        return 2

    service_dir = Path(sys.argv[1])
    src_dir = service_dir / "src"
    tests_dir = service_dir / "tests"

    if not src_dir.is_dir():
        print(f"::error::Folder {src_dir} not found")
        return 1

    sources = sorted(p for p in src_dir.rglob("*.py") if p.name != "__init__.py")
    if not sources:
        print(f"::error::No source files found in {src_dir}")
        return 1

    missing = []
    for source in sources:
        relative = source.relative_to(src_dir)
        expected = tests_dir / relative.parent / f"test_{relative.name}"
        if not expected.is_file():
            missing.append((source, expected))

    if missing:
        print("::error::Some source files have no matching test file:")
        for source, expected in missing:
            print(f"  - {source} -> missing {expected}")
        return 1

    print(f"OK: all {len(sources)} source files have a matching test file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())