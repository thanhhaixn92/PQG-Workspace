"""Fail closed when the E2-E backend constraints authority drifts."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CONSTRAINTS = BACKEND / "constraints-ci.txt"
PINNED_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^;\s]+)(?:\s*;\s*(?P<marker>.+))?$"
)


def load_constraints() -> dict[str, list[tuple[str, str | None]]]:
    entries: dict[str, list[tuple[str, str | None]]] = {}
    for raw_line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PINNED_REQUIREMENT.fullmatch(line)
        if match is None:
            raise AssertionError(f"constraint is not an exact pin: {line!r}")
        marker = match.group("marker")
        if marker:
            Marker(marker)
        name = canonicalize_name(match.group("name"))
        entries.setdefault(name, []).append((match.group("version"), marker))
    return entries


def main() -> int:
    if (BACKEND / "uv.lock").exists():
        raise AssertionError("backend/uv.lock remains a competing resolution authority")

    entries = load_constraints()
    if entries.get("pip") != [("26.2.1", None)]:
        raise AssertionError("constraints must pin the exact CI bootstrap pip==26.2.1")

    manifest = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    project = manifest["project"]
    declared = [*project["dependencies"], *project["optional-dependencies"]["dev"]]
    missing = {
        canonicalize_name(Requirement(requirement).name)
        for requirement in declared
        if canonicalize_name(Requirement(requirement).name) not in entries
    }
    if missing:
        raise AssertionError(f"constraints omit declared dependencies: {sorted(missing)}")

    build_names = {canonicalize_name(item) for item in manifest["build-system"]["requires"]}
    build_names.update({"pathspec", "tomlkit", "trove-classifiers"})
    missing_build = sorted(name for name in build_names if name not in entries)
    if missing_build:
        raise AssertionError(f"constraints omit build dependencies: {missing_build}")

    required_markers = {
        "pywin32": "sys_platform == 'win32'",
        "pywin32-ctypes": "sys_platform == 'win32'",
        "jeepney": "sys_platform == 'linux'",
        "secretstorage": "sys_platform == 'linux'",
    }
    for name, expected_marker in required_markers.items():
        if not any(marker == expected_marker for _, marker in entries.get(name, [])):
            raise AssertionError(f"{name} must retain marker {expected_marker!r}")
    if not any(marker and "sys_platform != 'win32'" in marker for _, marker in entries.get("uvloop", [])):
        raise AssertionError("uvloop must retain its non-Windows marker")

    print(f"PASS: validated {sum(map(len, entries.values()))} exact backend constraints")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
