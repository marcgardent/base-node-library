"""Multi-implementation conformance tests (conformance/manifest.json)."""

import json
from pathlib import Path

import pytest

from base_node import format_source, parse
from base_node.cli import main as cli_main

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "conformance" / "manifest.json"
CONFORMANCE_DIR = MANIFEST_PATH.parent


def load_manifest():
    assert MANIFEST_PATH.exists(), f"Manifest not found: {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_conformance_manifest_matches_bn_files():
    """Verify that every .bn file in the corpus matches the manifest."""
    manifest = load_manifest()
    assert manifest["version"] == "1.0"
    assert len(manifest["files"]) >= 3

    for entry in manifest["files"]:
        bn_path = CONFORMANCE_DIR / entry["file"]
        assert bn_path.exists(), f"Missing conformance file: {bn_path}"
        text = bn_path.read_text(encoding="utf-8")

        # 1. Parsing
        ast = parse(text, entry["file"])
        assert len(ast.graphs) == entry["graphs_count"], (
            f"{entry['file']}: expected {entry['graphs_count']} graphs, got {len(ast.graphs)}"
        )

        # 2. Check graphs, inputs, and outputs
        for expected_g, g in zip(entry["graphs"], ast.graphs):
            assert g.name == expected_g["name"]
            assert g.kind == expected_g["kind"]
            actual_inputs = [{"name": p.name, "type": p.type} for p in g.params]
            assert actual_inputs == expected_g["inputs"], (
                f"{entry['file']} graph {g.name}: non-conforming inputs"
            )
            actual_outputs = [{"name": r.name, "type": r.type} for r in g.outputs]
            assert actual_outputs == expected_g["outputs"], (
                f"{entry['file']} graph {g.name}: non-conforming outputs"
            )

        # 3. Check canonical formatting
        formatted = format_source(text)
        is_formatted = (text == formatted)
        assert is_formatted == entry["canonically_formatted"], (
            f"{entry['file']}: canonical_formatted mismatch (expected {entry['canonically_formatted']}, got {is_formatted})"
        )

        # 4. Format idempotency
        re_formatted = format_source(formatted)
        assert re_formatted == formatted, f"{entry['file']}: canonical formatting is not idempotent"


def test_cli_on_conformance_corpus():
    """Verify CLI behavior on the conformance corpus."""
    manifest = load_manifest()

    for entry in manifest["files"]:
        bn_path = str(CONFORMANCE_DIR / entry["file"])

        # parse
        ret_parse = cli_main(["parse", bn_path])
        assert ret_parse == 0

        # fmt --check
        ret_fmt = cli_main(["fmt", "--check", bn_path])
        expected_ret = 0 if entry["canonically_formatted"] else 1
        assert ret_fmt == expected_ret
