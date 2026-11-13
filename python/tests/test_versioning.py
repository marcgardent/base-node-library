"""Tests for language, stdlib, profiles, and package versioning."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

import base_node
from base_node import EDITION, STDLIB_VERSION, __version__, check_profile, load_profile, parse
from base_node.cli import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[2]
STDLIB_DIR = REPO_ROOT / "stdlib"
PROFILES_DIR = REPO_ROOT / "profiles"
MANIFEST_PATH = STDLIB_DIR / "manifest.json"


def test_package_version_constants():
    """Verify package version constants are defined and follow expected formats."""
    assert __version__ == "0.8.1"
    assert EDITION == "2026"
    assert STDLIB_VERSION == "0.8.1"


def test_cli_version_flag(capsys):
    """Verify base-node --version outputs formatted edition and versions."""
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    expected = f"base-node {__version__} (Language Edition {EDITION}, Stdlib {STDLIB_VERSION})"
    assert expected in captured.out or expected in captured.err


def test_profiles_versioning():
    """Verify all profile JSON files declare version, profile_version, and edition."""
    profile_files = list(PROFILES_DIR.glob("*.json"))
    assert len(profile_files) >= 5, "Expected at least 5 profiles in profiles/"

    for pf in profile_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        assert data.get("version") == 1, f"{pf.name} version must be integer schema 1"
        assert data.get("profile_version") == "0.8.1", f"{pf.name} profile_version mismatch"
        assert data.get("edition") == "2026", f"{pf.name} edition mismatch"


def test_stdlib_manifest_structure():
    """Verify stdlib/manifest.json conforms to the manifest contract."""
    assert MANIFEST_PATH.exists(), f"Missing {MANIFEST_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest.get("stdlib_version") == STDLIB_VERSION
    assert manifest.get("edition") == EDITION
    assert "modules" in manifest
    assert len(manifest["modules"]) >= 5


def test_stdlib_modules_match_manifest_and_headers():
    """Verify that every stdlib file has matching manifest entries and header annotations."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    modules = manifest["modules"]

    bn_files = {p.stem: p for p in STDLIB_DIR.glob("*.bn")}

    # 1. Manifest and files on disk are 1:1
    assert set(modules.keys()) == set(bn_files.keys()), (
        f"Manifest modules {set(modules.keys())} do not match files on disk {set(bn_files.keys())}"
    )

    header_re = re.compile(
        r"^//\s*@module\s+(?P<module>\w+)\s*\n"
        r"^//\s*@version\s+(?P<version>[\d\.]+)\s*\n"
        r"^//\s*@profile\s+(?P<profile>[\w-]+)\s*\n"
        r"^//\s*@edition\s+(?P<edition>\w+)",
        re.MULTILINE,
    )

    for mod_name, entry in modules.items():
        file_path = bn_files[mod_name]
        text = file_path.read_text(encoding="utf-8")

        # 2. Header annotations match manifest entry
        match = header_re.search(text)
        assert match is not None, f"Module {mod_name} ({file_path}) is missing required header annotations"

        header_data = match.groupdict()
        assert header_data["module"] == mod_name, f"{mod_name}: header module mismatch"
        assert header_data["version"] == entry["version"], f"{mod_name}: header version mismatch"
        assert header_data["profile"] == entry["profile"], f"{mod_name}: header profile mismatch"
        assert header_data["edition"] == entry["edition"], f"{mod_name}: header edition mismatch"

        # 3. Profile declared exists and is valid
        profile_data = load_profile(entry["profile"])
        assert profile_data["name"] == entry["profile"]

        # 4. AST parses and satisfies declared profile
        ast = parse(text, file_path.name)
        assert len(ast.graphs) > 0
        diagnostics = check_profile(ast, entry["profile"])
        assert diagnostics == [], f"{mod_name} has profile violations under {entry['profile']}: {diagnostics}"


def test_blender_extension_bundles_the_stdlib():
    """The Blender extension ships a copy of stdlib/: it must stay identical to it."""
    bundled = REPO_ROOT / "base-node-for-blender" / "stdlib"
    names = sorted(p.name for p in STDLIB_DIR.iterdir() if p.suffix in (".bn", ".json"))
    assert sorted(p.name for p in bundled.iterdir()) == names, "copy stdlib/ into base-node-for-blender/stdlib/"
    for name in names:
        assert (bundled / name).read_bytes() == (STDLIB_DIR / name).read_bytes(), \
            f"base-node-for-blender/stdlib/{name} differs from stdlib/{name}"
