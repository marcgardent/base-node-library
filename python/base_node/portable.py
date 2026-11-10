"""Socle portable Blender ⇄ Blade et contrat d'alias.

Définit le sous-ensemble portable du langage .bn partagé entre Blender (addons/bnodes)
et Blade (bf-nodes / bf-vector / bf-raster) :
- Types canoniques portables ;
- Entrées implicites portables ;
- Contrat d'alias (nom portable / nom Blender) ;
- Nœuds portables du socle commun (calcul, logique, courbes 2D, maillage 2D,
  attributs, switches, zones repeat et foreach, groupes) ;
- Fonction de validation check_portable(graphs) ;
- Fonction d'export dump_portable_schema(schema).
"""

import math
from typing import Any

# Types canoniques portables partagés entre Blender et Blade
PORTABLE_TYPES = (
    "Float",
    "Int",
    "Bool",
    "Vector",
    "Color",
    "Rotation",
    "Matrix",
    "String",
    "Menu",
    "Geometry",
    "Image",
    "Material",
)

# Entrées implicites portables
PORTABLE_IMPLICIT = ("Position", "Normal", "Index", "ID")

# Identifiants internes de socket d'interface correspondants dans Blender
PORTABLE_IMPLICIT_IDENTIFIERS = {"POSITION", "NORMAL", "INDEX", "ID_OR_INDEX"}

# Contrat d'alias entre le nom canonique portable et le nom Blender (host)
PORTABLE_ALIASES = {
    "WhiteNoise": "TexWhiteNoise",
    "TransformGeometry": "Transform",
    "CurveCircle": "CurvePrimitiveCircle",
    "CurveQuadrilateral": "CurvePrimitiveQuadrilateral",
    "CurveLine": "CurvePrimitiveLine",
    "BoundingBox": "BoundBox",
}

# Alias inverses : nom Blender -> nom canonique portable
BLENDER_TO_PORTABLE_ALIASES = {v: k for k, v in PORTABLE_ALIASES.items()}

# Genres d'arbres acceptés dans le socle portable
PORTABLE_KINDS = ("geometry", "vector", "pixel")

# Nœuds du socle commun 2D (noms canoniques portables)
CANONICAL_PORTABLE_NODES = (
    # Calcul mathématique / vectoriel, logique
    "Math",
    "VectorMath",
    "Compare",
    "BooleanMath",
    "Switch",
    "Mix",
    "MapRange",
    "Clamp",
    "CombineXYZ",
    "SeparateXYZ",
    "TexNoise",
    "WhiteNoise",
    "RandomValue",
    "VectorRotate",
    # Courbes 2D
    "CurveCircle",
    "CurveQuadrilateral",
    "CurveStar",
    "CurveLine",
    "CurveSpiral",
    "ResampleCurve",
    "TrimCurve",
    "SubdivideCurve",
    "ReverseCurve",
    "FillCurve",
    "FilletCurve",
    "SetCurveRadius",
    "CurveToMesh",
    "SplineParameter",
    "Tangent",
    "Radius",
    # Maillage & Points 2D
    "MeshGrid",
    "MeshCircle",
    "MeshLine",
    "Points",
    "Triangulate",
    # Géométrie 2D générale
    "SetPosition",
    "TransformGeometry",
    "JoinGeometry",
    "InstanceOnPoints",
    "RealizeInstances",
    "MergeByDistance",
    "BoundingBox",
    "SetMaterial",
    "SampleIndex",
    # Attributs & entrées contextuelles
    "CaptureAttribute",
    "StoreNamedAttribute",
    "NamedAttribute",
    "Position",
    "Normal",
    "Index",
    "ID",
    # Switches
    "IndexSwitch",
    "MenuSwitch",
)

# Tous les noms textuels reconnus (canoniques + noms Blender spécifiques)
PORTABLE_NODES = tuple(dict.fromkeys(CANONICAL_PORTABLE_NODES + tuple(PORTABLE_ALIASES.values())))

# Identifiants de classes de nœuds (bl_idname) autorisés dans un graphe portable
PORTABLE_BL_IDNAMES = {
    # Math & Logique
    "ShaderNodeMath",
    "ShaderNodeVectorMath",
    "FunctionNodeCompare",
    "FunctionNodeBooleanMath",
    "GeometryNodeSwitch",
    "ShaderNodeMix",
    "ShaderNodeMapRange",
    "ShaderNodeClamp",
    "ShaderNodeCombineXYZ",
    "ShaderNodeSeparateXYZ",
    "ShaderNodeTexNoise",
    "ShaderNodeTexWhiteNoise",
    "FunctionNodeRandomValue",
    "ShaderNodeVectorRotate",
    # Géométrie 2D & Courbes
    "GeometryNodeSetPosition",
    "GeometryNodeTransform",
    "GeometryNodeJoinGeometry",
    "GeometryNodeCurvePrimitiveCircle",
    "GeometryNodeCurvePrimitiveQuadrilateral",
    "GeometryNodeCurveStar",
    "GeometryNodeCurvePrimitiveLine",
    "GeometryNodeCurveSpiral",
    "GeometryNodeResampleCurve",
    "GeometryNodeTrimCurve",
    "GeometryNodeSubdivideCurve",
    "GeometryNodeReverseCurve",
    "GeometryNodeFillCurve",
    "GeometryNodeFilletCurve",
    "GeometryNodeSetCurveRadius",
    "GeometryNodeCurveToMesh",
    "GeometryNodeSplineParameter",
    "GeometryNodeInputTangent",
    "GeometryNodeInputRadius",
    "GeometryNodeMeshGrid",
    "GeometryNodeMeshCircle",
    "GeometryNodeMeshLine",
    "GeometryNodePoints",
    "GeometryNodeTriangulate",
    "GeometryNodeInstanceOnPoints",
    "GeometryNodeRealizeInstances",
    "GeometryNodeMergeByDistance",
    "GeometryNodeBoundBox",
    "GeometryNodeSetMaterial",
    "GeometryNodeSampleIndex",
    # Attributs & Contexte
    "GeometryNodeCaptureAttribute",
    "GeometryNodeStoreNamedAttribute",
    "GeometryNodeInputNamedAttribute",
    "GeometryNodeInputPosition",
    "GeometryNodeInputNormal",
    "GeometryNodeInputIndex",
    "GeometryNodeInputID",
    # Switches
    "GeometryNodeIndexSwitch",
    "GeometryNodeMenuSwitch",
    # Zones portables (repeat et foreach)
    "GeometryNodeRepeatInput",
    "GeometryNodeRepeatOutput",
    "GeometryNodeForeachGeometryElementInput",
    "GeometryNodeForeachGeometryElementOutput",
    # Structure de groupe
    "NodeGroupInput",
    "NodeGroupOutput",
    "GeometryNodeGroup",
    "group_input",
    "group_output",
    "NodeFrame",
    "NodeReroute",
}


def _plain(value: Any) -> Any:
    """Normalise les valeurs scalaires ou vectorielles pour le JSON."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 5)
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        return [_plain(v) for v in value]
    return value


class PortableSchema(dict):
    """Schéma portable Blender ⇄ Blade avec accès direct ou imbriqué."""

    @property
    def nodes(self) -> dict:
        return self.get("nodes", {})

    def __getitem__(self, key: str) -> Any:
        if super().__contains__(key):
            return super().__getitem__(key)
        nodes = super().get("nodes", {})
        if key in nodes:
            return nodes[key]
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or (
            super().__contains__("nodes") and key in super().get("nodes", {})
        )

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def check_portable(graphs: Any) -> list[str]:
    """Vérifie qu'une liste de ir.Graph compilés n'emploie que des types et des nœuds

    du contrat portable Blender ⇄ Blade.

    Retourne [] si tout est portable, sinon la liste des erreurs.
    """
    errors: list[str] = []
    if not isinstance(graphs, (list, tuple)):
        graphs = [graphs]

    for g in graphs:
        # 1. Type d'arbre
        if g.kind not in PORTABLE_KINDS:
            errors.append(
                f"Graphe '{g.name}' : type d'arbre '{g.kind}' non portable (attendu {PORTABLE_KINDS})"
            )

        # 2. Types des entrées / sorties de l'interface
        for name, typ in g.inputs:
            if typ not in PORTABLE_TYPES:
                errors.append(
                    f"Graphe '{g.name}' : entrée '{name}' de type non portable '{typ}'"
                )
        for name, typ in g.outputs:
            if typ not in PORTABLE_TYPES:
                errors.append(
                    f"Graphe '{g.name}' : sortie '{name}' de type non portable '{typ}'"
                )

        # 3. Entrées implicites
        for param, defs in g.defaults.items():
            if "implicit" in defs:
                impl = defs["implicit"]
                if (
                    impl not in PORTABLE_IMPLICIT
                    and impl not in PORTABLE_IMPLICIT_IDENTIFIERS
                ):
                    errors.append(
                        f"Graphe '{g.name}' : entrée implicite '{impl}' pour '{param}' non portable"
                    )

        # 4. Nœuds et zones
        for node in g.nodes:
            if node.bl_idname not in PORTABLE_BL_IDNAMES:
                errors.append(
                    f"Graphe '{g.name}' : nœud '{node.name or node.bl_idname}' "
                    f"(bl_idname '{node.bl_idname}') hors du contrat portable"
                )

            # Vérification des types des items (zones, capture attribute, etc.)
            if node.items:
                for item_name, item_type in node.items:
                    if item_type not in PORTABLE_TYPES:
                        errors.append(
                            f"Graphe '{g.name}' : item '{item_name}' du nœud '{node.bl_idname}' "
                            f"de type non portable '{item_type}'"
                        )
            if node.out_items:
                for item_name, item_type in node.out_items:
                    if item_type not in PORTABLE_TYPES:
                        errors.append(
                            f"Graphe '{g.name}' : sortie d'item '{item_name}' du nœud '{node.bl_idname}' "
                            f"de type non portable '{item_type}'"
                        )

    return errors


def dump_portable_schema(schema: Any) -> PortableSchema:
    """Extrait pour chaque nœud portable ses propriétés (props) et ses signatures

    de sockets par défaut (inputs, outputs).
    """
    nodes: dict[str, dict] = {}
    has_defaults = hasattr(schema, "defaults")

    for name in CANONICAL_PORTABLE_NODES:
        bl_name = PORTABLE_ALIASES.get(name, name)
        spec = schema.node("geometry", bl_name)
        if not spec:
            continue

        inputs, outputs = schema.sockets("geometry", spec, {})
        in_defs, prop_defs = (
            schema.defaults("geometry", spec, {}) if has_defaults else ({}, {})
        )

        props_dict = {}
        for p_name, prop in sorted(spec.props.items()):
            p_entry = {"kind": prop.kind}
            if prop.items:
                p_entry["items"] = list(prop.items)
            if p_name in prop_defs and prop_defs[p_name] is not None:
                p_entry["default"] = _plain(prop_defs[p_name])
            props_dict[p_name] = p_entry

        inputs_list = []
        for s in inputs:
            s_entry = {
                "name": s.name,
                "identifier": s.identifier,
                "type": s.type,
                "multi_input": bool(s.multi_input),
            }
            if s.identifier in in_defs and in_defs[s.identifier] is not None:
                s_entry["default"] = _plain(in_defs[s.identifier])
            inputs_list.append(s_entry)

        outputs_list = []
        for s in outputs:
            outputs_list.append(
                {
                    "name": s.name,
                    "identifier": s.identifier,
                    "type": s.type,
                }
            )

        entry = {
            "name": name,
            "bl_name": bl_name,
            "bl_idname": spec.bl_idname,
            "props": props_dict,
            "inputs": inputs_list,
            "outputs": outputs_list,
        }
        if name in PORTABLE_ALIASES:
            entry["alias_of"] = bl_name

        nodes[name] = entry

        # Si le nom Blender diffère, on référence également l'entrée par son nom Blender
        if bl_name != name and bl_name not in nodes:
            bl_entry = dict(entry)
            bl_entry["name"] = bl_name
            bl_entry["canonical_name"] = name
            nodes[bl_name] = bl_entry

    return PortableSchema(
        {
            "version": 1,
            "types": list(PORTABLE_TYPES),
            "implicit": list(PORTABLE_IMPLICIT),
            "aliases": dict(PORTABLE_ALIASES),
            "nodes": nodes,
        }
    )
