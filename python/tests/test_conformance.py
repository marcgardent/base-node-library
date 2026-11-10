"""Tests de conformité multi-implémentation (conformance/manifest.json)."""

import json
from pathlib import Path

import pytest

from base_node import format_source, parse
from base_node.cli import main as cli_main

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "conformance" / "manifest.json"
CONFORMANCE_DIR = MANIFEST_PATH.parent


def load_manifest():
    assert MANIFEST_PATH.exists(), f"Manifeste introuvable : {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_conformance_manifest_matches_bn_files():
    """Vérifie que chaque fichier .bn du corpus respecte le manifeste."""
    manifest = load_manifest()
    assert manifest["version"] == "1.0"
    assert len(manifest["files"]) >= 3

    for entry in manifest["files"]:
        bn_path = CONFORMANCE_DIR / entry["file"]
        assert bn_path.exists(), f"Fichier de conformité manquant : {bn_path}"
        text = bn_path.read_text(encoding="utf-8")

        # 1. Analyse syntaxique
        ast = parse(text, entry["file"])
        assert len(ast.graphs) == entry["graphs_count"], (
            f"{entry['file']}: attendu {entry['graphs_count']} graphes, obtenu {len(ast.graphs)}"
        )

        # 2. Vérification des graphes, entrées et sorties
        for expected_g, g in zip(entry["graphs"], ast.graphs):
            assert g.name == expected_g["name"]
            assert g.kind == expected_g["kind"]
            actual_inputs = [{"name": p.name, "type": p.type} for p in g.params]
            assert actual_inputs == expected_g["inputs"], (
                f"{entry['file']} graphe {g.name}: inputs non conformes"
            )
            actual_outputs = [{"name": r.name, "type": r.type} for r in g.outputs]
            assert actual_outputs == expected_g["outputs"], (
                f"{entry['file']} graphe {g.name}: outputs non conformes"
            )

        # 3. Vérification du formatage canonique
        formatted = format_source(text)
        is_formatted = (text == formatted)
        assert is_formatted == entry["canonically_formatted"], (
            f"{entry['file']}: canonical_formatted mismatch (attendu {entry['canonically_formatted']}, obtenu {is_formatted})"
        )

        # 4. Idempotence du formatage
        re_formatted = format_source(formatted)
        assert re_formatted == formatted, f"{entry['file']}: le formatage canonique n'est pas idempotent"


def test_cli_on_conformance_corpus():
    """Vérifie le comportement de la CLI sur le corpus de conformité."""
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
