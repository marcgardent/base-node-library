"""Test de l'extension Blender base_node et de l'alias bnodes.

Exécuté dans Blender via :
    blender --background --factory-startup --python-exit-code 1 --python base-node-for-blender/tests/test_extension.py
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

EXT_DIR = Path(__file__).resolve().parents[1]
LIB_ROOT = EXT_DIR.parent
STDLIB_DIR = LIB_ROOT / "stdlib"

_spec = importlib.util.spec_from_file_location(
    "base_node", EXT_DIR / "__init__.py", submodule_search_locations=[str(EXT_DIR)]
)
base_node = importlib.util.module_from_spec(_spec)
sys.modules["base_node"] = base_node
_spec.loader.exec_module(base_node)

import bpy
import bnodes


def test_import_and_aliases():
    """1. Vérifie l'import de base_node et de l'alias bnodes."""
    print("-> Test 1 : Vérification des imports et alias...")
    assert base_node is not None, "base_node introuvable"
    assert bnodes is not None, "bnodes introuvable"
    assert base_node is bnodes, "bnodes n'est pas un alias de base_node"
    assert base_node.lang is bnodes.lang, "base_node.lang et bnodes.lang diffèrent"
    assert base_node.host is bnodes.host, "base_node.host et bnodes.host diffèrent"

    # Enregistrement et désenregistrement de l'addon
    base_node.register()
    assert hasattr(bpy.types.NodeTree, "base_node_text"), "NodeTree.base_node_text manquant"
    assert hasattr(bpy.types.NodeTree, "bnodes_text"), "NodeTree.bnodes_text manquant"
    assert hasattr(bpy.types.WindowManager, "base_node_sync"), "WindowManager.base_node_sync manquant"
    assert hasattr(bpy.types.WindowManager, "bnodes_sync"), "WindowManager.bnodes_sync manquant"
    print("   ✓ Imports et alias validés")


def test_check_profile_stdlib():
    """2. Vérifie la conformité de chaque module stdlib selon son profil cible."""
    print("-> Test 2 : Vérification des profils sur stdlib...")
    from base_node.host.schema import BlenderSchema
    from base_node.lang import compile_source
    from base_node.lang.profiles import check_profile

    targets = [
        ("maths.bn", "core"),
        ("sdf2d.bn", "sdf2d"),
        ("courbes2d.bn", "vector2d"),
        ("motifs2d.bn", "vector2d"),
        ("gp_outils2d.bn", "vector2d"),
    ]

    def loader(name: str, _caller: str):
        p = STDLIB_DIR / f"{name}.bn"
        if not p.exists():
            raise LookupError(f"Module stdlib introuvable : {p}")
        return p.read_text(encoding="utf-8"), str(p)

    with BlenderSchema() as schema:
        for filename, expected_profile in targets:
            filepath = STDLIB_DIR / filename
            assert filepath.exists(), f"Fichier manquant : {filepath}"
            source = filepath.read_text(encoding="utf-8")

            graphs = compile_source(source, schema, str(filepath), load=loader)
            assert len(graphs) > 0, f"Aucun graphe compilé pour {filename}"

            errors = check_profile(graphs, profile=expected_profile)
            assert errors == [], f"Erreurs dans {filename} pour le profil '{expected_profile}' :\n" + "\n".join(errors)
            print(f"   ✓ {filename} ({len(graphs)} graphes) validé sous profil '{expected_profile}'")


def test_build_and_round_trip():
    """3. Construction et aller-retour Tree → Text → Tree dans Blender."""
    print("-> Test 3 : Construction et aller-retour Tree → Text → Tree...")
    from base_node.host import build_source, export_tree

    src = """
geometry graph ondulation(geometry: Geometry, frequence: Float = 2.0, amplitude: Float = 0.5) -> Geometry {
  "Ondulation de la surface le long de Z"
  p = Position()
  h = sin(p.x * frequence) * amplitude
  return SetPosition(geometry, offset: CombineXYZ(z: h))
}
"""

    # 1. Text -> Tree
    trees = build_source(src, filename="ondulation.bn")
    assert len(trees) == 1, f"Attendu 1 arbre construit, obtenu {len(trees)}"
    tree = trees[0]
    assert tree.name == "ondulation", f"Nom d'arbre inattendu : {tree.name}"
    assert len(tree.nodes) > 0, "L'arbre construit ne contient aucun nœud"

    # Vérification des propriétés attachées
    assert hasattr(tree, "bnodes_text"), "Propriété bnodes_text absente sur le node group"
    assert hasattr(tree, "base_node_text"), "Propriété base_node_text absente sur le node group"

    # 2. Tree -> Text
    exported, warnings = export_tree(tree)
    assert "geometry graph ondulation" in exported, f"En-tête absent dans l'export :\n{exported}"
    assert "SetPosition" in exported, f"SetPosition absent dans l'export :\n{exported}"

    # 3. Text -> Tree (deuxième passe)
    rebuilt_trees = build_source(exported, filename="ondulation_rebuilt.bn")
    assert len(rebuilt_trees) == 1
    rebuilt_tree = rebuilt_trees[0]
    assert rebuilt_tree.name == "ondulation"

    re_exported, _ = export_tree(rebuilt_tree)
    assert re_exported == exported, "L'aller-retour Tree → Text n'est pas stable"
    print("   ✓ Aller-retour Tree → Text → Tree validé")


def main():
    print("=== Démarrage des tests de l'extension Base Node pour Blender ===")
    tests = [
        test_import_and_aliases,
        test_check_profile_stdlib,
        test_build_and_round_trip,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception:
            failed += 1
            traceback.print_exc()

    if failed:
        print(f"\n❌ ÉCHEC : {failed} test(s) échoué(s)")
        sys.exit(1)
    else:
        print(f"\n✅ SUCCÈS : 100% des tests ({len(tests)}/{len(tests)}) validés avec succès !")
        sys.exit(0)


if __name__ == "__main__":
    main()
