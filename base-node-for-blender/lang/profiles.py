"""Declarative compatibility profiles for Base Node (.bn).

Handles hierarchical profile loading (extends) in profiles/<name>.json
and syntax and semantic validation of compiled or AST graphs (check_profile).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import key

# Internal implicit input identifiers in Blender Geometry Nodes
IMPLICIT_MAP = {
    "Position": {"Position", "POSITION"},
    "Normal": {"Normal", "NORMAL"},
    "Index": {"Index", "INDEX"},
    "ID": {"ID", "ID_OR_INDEX"},
}

CANONICAL_TO_BL_IDNAME: dict[str, str] = {
    "BooleanMath": "FunctionNodeBooleanMath",
    "BoundBox": "GeometryNodeBoundBox",
    "BoundingBox": "GeometryNodeBoundBox",
    "CaptureAttribute": "GeometryNodeCaptureAttribute",
    "Clamp": "ShaderNodeClamp",
    "CombineXYZ": "ShaderNodeCombineXYZ",
    "Compare": "FunctionNodeCompare",
    "CurveCircle": "GeometryNodeCurvePrimitiveCircle",
    "CurveEndpointSelection": "GeometryNodeCurveEndpointSelection",
    "CurveHandlePositions": "GeometryNodeInputCurveHandlePositions",
    "CurveHandleTypeSelection": "GeometryNodeCurveHandleTypeSelection",
    "CurveLength": "GeometryNodeCurveLength",
    "CurveLine": "GeometryNodeCurvePrimitiveLine",
    "CurveOfPoint": "GeometryNodeCurveOfPoint",
    "CurvePrimitiveCircle": "GeometryNodeCurvePrimitiveCircle",
    "CurvePrimitiveLine": "GeometryNodeCurvePrimitiveLine",
    "CurvePrimitiveQuadrilateral": "GeometryNodeCurvePrimitiveQuadrilateral",
    "CurveQuadrilateral": "GeometryNodeCurvePrimitiveQuadrilateral",
    "CurvesToGreasePencil": "GeometryNodeCurvesToGreasePencil",
    "CurveSpiral": "GeometryNodeCurveSpiral",
    "CurveStar": "GeometryNodeCurveStar",
    "CurveTilt": "GeometryNodeInputCurveTilt",
    "CurveToMesh": "GeometryNodeCurveToMesh",
    "CurveToPoints": "GeometryNodeCurveToPoints",
    "FillCurve": "GeometryNodeFillCurve",
    "FilletCurve": "GeometryNodeFilletCurve",
    "GreasePencilColor": "GeometryNodeGreasePencilColor",
    "GreasePencilDrawTime": "GeometryNodeGreasePencilDrawTime",
    "GreasePencilFillID": "GeometryNodeGreasePencilFillID",
    "GreasePencilOpacity": "GeometryNodeGreasePencilOpacity",
    "GreasePencilStrokeSoftness": "GeometryNodeGreasePencilStrokeSoftness",
    "GreasePencilStrokeVisibility": "GeometryNodeGreasePencilStrokeVisibility",
    "GreasePencilToCurves": "GeometryNodeGreasePencilToCurves",
    "ID": "GeometryNodeInputID",
    "Index": "GeometryNodeInputIndex",
    "IndexSwitch": "GeometryNodeIndexSwitch",
    "InstanceOnPoints": "GeometryNodeInstanceOnPoints",
    "InterpolateCurves": "GeometryNodeInterpolateCurves",
    "JoinGeometry": "GeometryNodeJoinGeometry",
    "MapRange": "ShaderNodeMapRange",
    "Math": "ShaderNodeMath",
    "MenuSwitch": "GeometryNodeMenuSwitch",
    "MergeByDistance": "GeometryNodeMergeByDistance",
    "MeshCircle": "GeometryNodeMeshCircle",
    "MeshGrid": "GeometryNodeMeshGrid",
    "MeshLine": "GeometryNodeMeshLine",
    "Mix": "ShaderNodeMix",
    "NamedAttribute": "GeometryNodeInputNamedAttribute",
    "Normal": "GeometryNodeInputNormal",
    "OffsetPointInCurve": "GeometryNodeOffsetPointInCurve",
    "Points": "GeometryNodePoints",
    "PointsOfCurve": "GeometryNodePointsOfCurve",
    "PointsToCurves": "GeometryNodePointsToCurves",
    "Position": "GeometryNodeInputPosition",
    "Radius": "GeometryNodeInputRadius",
    "RandomValue": "FunctionNodeRandomValue",
    "RealizeInstances": "GeometryNodeRealizeInstances",
    "ResampleCurve": "GeometryNodeResampleCurve",
    "ReverseCurve": "GeometryNodeReverseCurve",
    "SampleCurve": "GeometryNodeSampleCurve",
    "SampleIndex": "GeometryNodeSampleIndex",
    "SeparateXYZ": "ShaderNodeSeparateXYZ",
    "SetCurveHandlePositions": "GeometryNodeSetCurveHandlePositions",
    "SetCurveNormal": "GeometryNodeSetCurveNormal",
    "SetCurveRadius": "GeometryNodeSetCurveRadius",
    "SetCurveTilt": "GeometryNodeSetCurveTilt",
    "SetGreasePencilColor": "GeometryNodeSetGreasePencilColor",
    "SetGreasePencilDepth": "GeometryNodeSetGreasePencilDepth",
    "SetGreasePencilSoftness": "GeometryNodeSetGreasePencilSoftness",
    "SetMaterial": "GeometryNodeSetMaterial",
    "SetPosition": "GeometryNodeSetPosition",
    "SplineParameter": "GeometryNodeSplineParameter",
    "StoreNamedAttribute": "GeometryNodeStoreNamedAttribute",
    "SubdivideCurve": "GeometryNodeSubdivideCurve",
    "Switch": "GeometryNodeSwitch",
    "Tangent": "GeometryNodeInputTangent",
    "TexNoise": "ShaderNodeTexNoise",
    "TexWhiteNoise": "ShaderNodeTexWhiteNoise",
    "Transform": "GeometryNodeTransform",
    "TransformGeometry": "GeometryNodeTransform",
    "Triangulate": "GeometryNodeTriangulate",
    "TrimCurve": "GeometryNodeTrimCurve",
    "VectorMath": "ShaderNodeVectorMath",
    "VectorRotate": "ShaderNodeVectorRotate",
    "WhiteNoise": "ShaderNodeTexWhiteNoise",
}

ZONE_BL_IDNAMES: dict[str, set[str]] = {
    "repeat": {"GeometryNodeRepeatInput", "GeometryNodeRepeatOutput"},
    "foreach": {"GeometryNodeForeachGeometryElementInput", "GeometryNodeForeachGeometryElementOutput"},
    "simulate": {"GeometryNodeSimulationInput", "GeometryNodeSimulationOutput"},
    "closure": {"GeometryNodeClosureInput", "GeometryNodeClosureOutput"},
}

PLUMBING_BL_IDNAMES: set[str] = {
    "NodeGroupInput",
    "NodeGroupOutput",
    "GeometryNodeGroup",
    "group_input",
    "group_output",
    "NodeFrame",
    "NodeReroute",
}

# Builtin fallback profiles
BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "core": {
        "name": "core",
        "version": 1,
        "description": "Pure mathematical and logical profile, universally portable",
        "extends": None,
        "kinds": ["geometry", "vector", "pixel"],
        "types": [
            "Float", "Int", "Bool", "Vector", "Color", "Rotation", "Matrix", "String", "Menu"
        ],
        "implicit": ["Position", "Normal", "Index", "ID"],
        "aliases": {
            "WhiteNoise": "TexWhiteNoise",
            "TransformGeometry": "Transform",
            "CurveCircle": "CurvePrimitiveCircle",
            "CurveQuadrilateral": "CurvePrimitiveQuadrilateral",
            "CurveLine": "CurvePrimitiveLine",
            "BoundingBox": "BoundBox",
        },
        "zones": ["repeat"],
        "nodes": [
            "Math", "VectorMath", "Compare", "BooleanMath", "Switch", "Mix",
            "MapRange", "Clamp", "CombineXYZ", "SeparateXYZ", "TexNoise",
            "WhiteNoise", "RandomValue", "VectorRotate"
        ],
    },
    "sdf2d": {
        "name": "sdf2d",
        "version": 1,
        "description": "2D signed distance field (SDF) profile",
        "extends": "core",
        "implicit": ["Position", "Normal", "Index", "ID"],
        "nodes": ["Position", "Normal", "Index", "ID"],
    },
    "vector2d": {
        "name": "vector2d",
        "version": 1,
        "description": "2D vector profile (curves, 2D meshes, point clouds, attributes)",
        "extends": "sdf2d",
        "types": ["Geometry", "Material"],
        "zones": ["foreach"],
        "nodes": [
            "CurveCircle", "CurveQuadrilateral", "CurveStar", "CurveLine", "CurveSpiral",
            "ResampleCurve", "TrimCurve", "SubdivideCurve", "ReverseCurve", "FillCurve",
            "FilletCurve", "SetCurveRadius", "CurveToMesh", "SplineParameter", "Tangent",
            "Radius", "MeshGrid", "MeshCircle", "MeshLine", "Points", "Triangulate",
            "SetPosition", "TransformGeometry", "JoinGeometry", "InstanceOnPoints",
            "RealizeInstances", "MergeByDistance", "BoundingBox", "SampleIndex",
            "CaptureAttribute", "StoreNamedAttribute", "NamedAttribute",
            "IndexSwitch", "MenuSwitch", "SetMaterial"
        ],
    },
    "ink2d": {
        "name": "ink2d",
        "version": 1,
        "description": "2D living ink, Grease Pencil strokes, dynamics, and attributes (extends vector2d)",
        "extends": "vector2d",
        "types": ["Geometry", "Material"],
        "zones": ["foreach"],
        "nodes": [
            "GreasePencilDrawTime", "GreasePencilOpacity", "GreasePencilColor",
            "GreasePencilFillID", "GreasePencilStrokeSoftness", "GreasePencilStrokeVisibility",
            "GreasePencilToCurves", "CurvesToGreasePencil", "SetGreasePencilColor",
            "SetGreasePencilDepth", "SetGreasePencilSoftness", "CurveTilt", "SetCurveTilt",
            "SampleCurve", "CurveLength", "CurveToPoints", "PointsToCurves",
            "InterpolateCurves", "OffsetPointInCurve", "CurveOfPoint", "PointsOfCurve",
            "CurveEndpointSelection", "CurveHandleTypeSelection", "CurveHandlePositions",
            "SetCurveHandlePositions", "SetCurveNormal"
        ],
    },
    "raster2d": {
        "name": "raster2d",
        "version": 1,
        "description": "2D raster / image profile",
        "extends": "sdf2d",
        "types": ["Image"],
        "nodes": [
            "Flatten", "Classifier", "ClassColors", "SeparateColor", "CombineColor",
            "SetPixel", "Blur", "Blend", "Vectorize", "Rasterize"
        ],
    },
    "blender-geometry": {
        "name": "blender-geometry",
        "version": 1,
        "description": "Full Blender Geometry Nodes host profile (5.2+ / 5.3+)",
        "extends": "ink2d",
        "allow_all_blender_nodes": True,
        "zones": ["simulate", "closure"],
        "types": ["Bundle", "Closure", "Object", "Collection", "Texture"],
    },
}


def _find_profile_file(name: str) -> Path | None:
    """Find the JSON file corresponding to the specified profile."""
    # Direct path
    p = Path(name)
    if p.is_file():
        return p
    if not name.endswith(".json"):
        p_json = Path(f"{name}.json")
        if p_json.is_file():
            return p_json

    # Search in common profile directories
    candidates = [
        Path.cwd() / "profiles" / f"{name}.json",
        Path(__file__).resolve().parents[2] / "profiles" / f"{name}.json",
        Path(__file__).resolve().parent / "profiles" / f"{name}.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_profile(name: str) -> dict[str, Any]:
    """Load a compatibility profile resolving the 'extends' inheritance chain."""
    base_name = name[:-5] if name.endswith(".json") else name

    profile_file = _find_profile_file(name)
    if profile_file is not None:
        data = json.loads(profile_file.read_text(encoding="utf-8"))
    elif base_name in BUILTIN_PROFILES:
        data = dict(BUILTIN_PROFILES[base_name])
    else:
        raise ValueError(f"Unknown profile: '{name}'")

    parent_name = data.get("extends")
    if parent_name:
        parent = load_profile(parent_name)
        # Recursive merge
        resolved: dict[str, Any] = {
            "name": data.get("name", base_name),
            "version": data.get("version", parent.get("version", 1)),
            "description": data.get("description", parent.get("description", "")),
            "extends": parent_name,
            "kinds": list(dict.fromkeys(parent.get("kinds", []) + data.get("kinds", []))),
            "types": list(dict.fromkeys(parent.get("types", []) + data.get("types", []))),
            "implicit": list(dict.fromkeys(parent.get("implicit", []) + data.get("implicit", []))),
            "aliases": {**parent.get("aliases", {}), **data.get("aliases", {})},
            "zones": list(dict.fromkeys(parent.get("zones", []) + data.get("zones", []))),
            "nodes": list(dict.fromkeys(parent.get("nodes", []) + data.get("nodes", []))),
            "allow_all_blender_nodes": data.get(
                "allow_all_blender_nodes", parent.get("allow_all_blender_nodes", False)
            ),
        }
    else:
        resolved = {
            "name": data.get("name", base_name),
            "version": data.get("version", 1),
            "description": data.get("description", ""),
            "extends": None,
            "kinds": list(data.get("kinds", ["geometry", "vector", "pixel"])),
            "types": list(data.get("types", [])),
            "implicit": list(data.get("implicit", [])),
            "aliases": dict(data.get("aliases", {})),
            "zones": list(data.get("zones", [])),
            "nodes": list(data.get("nodes", [])),
            "allow_all_blender_nodes": bool(data.get("allow_all_blender_nodes", False)),
        }

    # Compute allowed bl_idnames
    allowed_bl_ids: set[str] = set(PLUMBING_BL_IDNAMES)
    for z in resolved.get("zones", []):
        if z in ZONE_BL_IDNAMES:
            allowed_bl_ids.update(ZONE_BL_IDNAMES[z])

    aliases = resolved.get("aliases", {})
    for node_name in resolved.get("nodes", []):
        if node_name in CANONICAL_TO_BL_IDNAME:
            allowed_bl_ids.add(CANONICAL_TO_BL_IDNAME[node_name])
        elif node_name in aliases and aliases[node_name] in CANONICAL_TO_BL_IDNAME:
            allowed_bl_ids.add(CANONICAL_TO_BL_IDNAME[aliases[node_name]])
        else:
            allowed_bl_ids.add(node_name)

    resolved["_allowed_bl_idnames"] = allowed_bl_ids

    # Compute allowed implicit identifiers
    allowed_impls: set[str] = set()
    for imp in resolved.get("implicit", []):
        if imp in IMPLICIT_MAP:
            allowed_impls.update(IMPLICIT_MAP[imp])
        else:
            allowed_impls.add(imp)
    resolved["_allowed_implicits"] = allowed_impls

    return resolved


BUILTIN_MATH_FUNCS: set[str] = {
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh",
    "pow", "exp", "log", "sqrt", "inv_sqrt", "abs", "min", "max", "clamp", "sign",
    "floor", "ceil", "round", "trunc", "fract", "mod", "fmod", "radians", "degrees",
    "dot", "cross", "length", "distance", "normalize", "reflect", "refract", "project", "scale",
}

PROFILE_ASCENT_CHAIN: list[str] = [
    "core",
    "sdf2d",
    "vector2d",
    "ink2d",
    "blender-geometry",
]

PROFILE_RANKS: dict[str, int] = {
    "core": 0,
    "sdf2d": 1,
    "vector2d": 2,
    "raster2d": 2,
    "ink2d": 3,
    "blender-geometry": 4,
}

STDLIB_MODULE_PROFILES: dict[str, str] = {
    "math": "core",
    "sdf2d": "sdf2d",
    "curves2d": "vector2d",
    "patterns2d": "vector2d",
    "planar2d": "vector2d",
    "fillet2d": "vector2d",
    "hachures2d": "vector2d",
    "deform2d": "vector2d",
    "ink2d": "ink2d",
}


def check_profile(graphs: Any, profile: str | dict[str, Any] = "vector2d") -> list[str]:
    """Check that a list of graphs (IR or AST) conforms to profile constraints.

    Returns [] if all graphs conform, otherwise a list of error messages.
    """
    if isinstance(profile, str):
        prof = load_profile(profile)
    else:
        prof = profile
        if "_allowed_bl_idnames" not in prof:
            prof = load_profile(prof.get("name", "core"))

    errors: list[str] = []
    file_uses: list[Any] = []
    if hasattr(graphs, "uses"):
        file_uses = getattr(graphs, "uses", [])
    if hasattr(graphs, "graphs"):
        graphs = graphs.graphs
    elif not isinstance(graphs, (list, tuple)):
        graphs = [graphs]

    allowed_kinds = set(prof.get("kinds", ["geometry", "vector", "pixel"]))
    allowed_types = set(prof.get("types", []))
    allowed_implicits = prof.get("_allowed_implicits", set())
    allowed_bl_idnames = prof.get("_allowed_bl_idnames", set())
    allowed_zones = set(prof.get("zones", []))
    prof_nodes = set(prof.get("nodes", []))
    aliases = dict(prof.get("aliases", {}))
    for a, target in list(aliases.items()):
        if target in prof_nodes:
            prof_nodes.add(a)
        if a in prof_nodes:
            prof_nodes.add(target)

    allow_all = prof.get("allow_all_blender_nodes", False)

    imported_modules: set[str] = set()
    imported_names: set[str] = set()
    wildcard_import = False
    for u in file_uses:
        imported_modules.add(u.name)
        if getattr(u, "alias", None):
            imported_modules.add(u.alias)
        if getattr(u, "names", None):
            for n in u.names:
                imported_names.add(n)
                imported_names.add(f"{u.name}::{n}")
                if getattr(u, "alias", None):
                    imported_names.add(f"{u.alias}::{n}")
        else:
            wildcard_import = True

        if u.name in STDLIB_MODULE_PROFILES and not allow_all:
            req_prof = STDLIB_MODULE_PROFILES[u.name]
            if PROFILE_RANKS.get(req_prof, 0) > PROFILE_RANKS.get(prof["name"], 0):
                errors.append(
                    f"Imported module '{u.name}' requires profile '{req_prof}' (exceeds profile '{prof['name']}')"
                )

    declared_graphs: set[str] = set()
    for g in graphs:
        if hasattr(g, "name"):
            declared_graphs.add(g.name)
            declared_graphs.add(key(g.name))

    for g in graphs:
        # Check tree kind
        if g.kind not in allowed_kinds:
            errors.append(
                f"Graph '{g.name}': tree kind '{g.kind}' not allowed by profile '{prof['name']}' (expected {sorted(allowed_kinds)})"
            )

        # Check interface inputs / outputs
        # Compatible with IR (g.inputs: list[tuple[name, type]]) and AST (g.params: list[Param])
        def _extract_params(items: Any) -> list[tuple[str, str]]:
            res: list[tuple[str, str]] = []
            for item in items or ():
                if isinstance(item, tuple) and len(item) == 2:
                    res.append(item)
                elif hasattr(item, "items"):  # ast.Panel
                    res.extend(_extract_params(item.items))
                elif hasattr(item, "name") and hasattr(item, "type"):  # ast.Param
                    res.append((item.name, item.type))
            return res

        inputs = _extract_params(g.inputs if hasattr(g, "inputs") else getattr(g, "params", ()))
        outputs = _extract_params(getattr(g, "outputs", ()))

        for name, typ in inputs:
            if typ not in allowed_types:
                errors.append(
                    f"Graph '{g.name}': input '{name}' of type '{typ}' not allowed by profile '{prof['name']}'"
                )
        for name, typ in outputs:
            if typ not in allowed_types:
                errors.append(
                    f"Graph '{g.name}': output '{name}' of type '{typ}' not allowed by profile '{prof['name']}'"
                )

        # Check implicit inputs
        defaults = getattr(g, "defaults", {})
        for param, defs in defaults.items():
            if isinstance(defs, dict) and "implicit" in defs:
                impl = defs["implicit"]
                if impl not in allowed_implicits:
                    errors.append(
                        f"Graph '{g.name}': implicit input '{impl}' for '{param}' not allowed by profile '{prof['name']}'"
                    )

        if hasattr(g, "params"):
            for p in g.params:
                d = getattr(p, "default", None)
                if d is not None and hasattr(d, "name") and d.name in ("Position", "Normal", "Index", "ID"):
                    if d.name not in allowed_implicits:
                        errors.append(
                            f"Graph '{g.name}': implicit input '{d.name}' for '{p.name}' not allowed by profile '{prof['name']}'"
                        )

        # Check nodes (IR)
        if hasattr(g, "nodes") and not allow_all:
            for node in g.nodes:
                bl_id = getattr(node, "bl_idname", "")
                node_name = getattr(node, "name", "") or bl_id
                if bl_id not in allowed_bl_idnames and node_name not in allowed_bl_idnames:
                    errors.append(
                        f"Graph '{g.name}': node '{node_name}' (bl_idname '{bl_id}') outside profile '{prof['name']}'"
                    )

                # Check types of internal items
                for item_name, item_type in getattr(node, "items", ()) or ():
                    if item_type not in allowed_types:
                        errors.append(
                            f"Graph '{g.name}': item '{item_name}' of node '{bl_id}' has non-allowed type '{item_type}'"
                        )
                for item_name, item_type in getattr(node, "out_items", ()) or ():
                    if item_type not in allowed_types:
                        errors.append(
                            f"Graph '{g.name}': item output '{item_name}' of node '{bl_id}' has non-allowed type '{item_type}'"
                        )

        # Check statements and calls (AST)
        if hasattr(g, "body") and not allow_all:
            def check_expr(expr: Any) -> None:
                if expr is None:
                    return
                if hasattr(expr, "name") and hasattr(expr, "args"):  # Call
                    call_name = expr.name
                    if call_name in BUILTIN_MATH_FUNCS:
                        pass
                    elif "::" in call_name:
                        mod_part = call_name.split("::", 1)[0]
                        if mod_part in imported_modules or wildcard_import:
                            pass
                        elif call_name not in allowed_bl_idnames and call_name not in prof_nodes:
                            errors.append(
                                f"Graph '{g.name}': call '{call_name}' outside profile '{prof['name']}'"
                            )
                    elif call_name in declared_graphs or call_name in imported_names or wildcard_import:
                        pass
                    elif (
                        call_name not in allowed_bl_idnames
                        and call_name not in prof_nodes
                        and call_name not in aliases
                    ):
                        errors.append(
                            f"Graph '{g.name}': node or function '{call_name}' not allowed by profile '{prof['name']}'"
                        )
                    for a in getattr(expr, "args", ()):
                        check_expr(getattr(a, "value", None))
                elif hasattr(expr, "left") and hasattr(expr, "call"):  # Pipe
                    check_expr(expr.left)
                    check_expr(expr.call)
                elif hasattr(expr, "left") and hasattr(expr, "right"):  # BinOp
                    check_expr(expr.left)
                    check_expr(expr.right)
                elif hasattr(expr, "value"):  # Neg, Not, etc.
                    check_expr(expr.value)
                elif hasattr(expr, "target"):  # Member
                    check_expr(expr.target)
                elif hasattr(expr, "items"):  # Tuple
                    for it in expr.items:
                        check_expr(it)

            def check_stmt(s: Any) -> None:
                if hasattr(s, "value"):  # Assign or Return
                    val = s.value
                    if hasattr(val, "body") and hasattr(val, "name"):  # Zone
                        zname = val.name.lower()
                        if zname not in allowed_zones:
                            errors.append(
                                f"Graph '{g.name}': zone '{zname}' not allowed by profile '{prof['name']}'"
                            )
                        for inner in val.body:
                            check_stmt(inner)
                    elif hasattr(val, "fields"):  # Record return
                        for f in val.fields:
                            check_expr(getattr(f, "value", None))
                    else:
                        check_expr(val)
                elif hasattr(s, "body"):  # Frame
                    for inner in s.body:
                        check_stmt(inner)

            for s in g.body:
                check_stmt(s)

    return errors


def solve_minimal_profile(graphs: Any, candidate_chain: list[str] | None = None) -> str:
    """Infer the minimal generic compatibility profile for a graph or list of graphs.

    Tests profiles in ascending order (core -> sdf2d -> vector2d -> ink2d -> blender-geometry)
    and returns the earliest profile for which all constraints pass with 0 errors.
    """
    chain = candidate_chain or PROFILE_ASCENT_CHAIN
    for prof_name in chain:
        errs = check_profile(graphs, profile=prof_name)
        if not errs:
            return prof_name
    return "blender-geometry"


def analyze_profile_ascent(
    graphs: Any, candidate_chain: list[str] | None = None
) -> dict[str, Any]:
    """Detailed analysis of profile ascent compatibility.

    Returns:
        minimal_profile: the minimal conforming profile
        tested: dict of {profile_name: list_of_errors}
        barriers: dict of {profile_name: list_of_errors} for profiles lower than minimal
        chain: list of evaluated profile names in order
    """
    chain = candidate_chain or PROFILE_ASCENT_CHAIN
    tested: dict[str, list[str]] = {}
    minimal = "blender-geometry"
    found = False

    for prof_name in chain:
        errs = check_profile(graphs, profile=prof_name)
        tested[prof_name] = errs
        if not errs and not found:
            minimal = prof_name
            found = True

    barriers: dict[str, list[str]] = {}
    for prof_name in chain:
        if prof_name == minimal:
            break
        barriers[prof_name] = tested.get(prof_name, [])

    return {
        "minimal_profile": minimal,
        "tested": tested,
        "barriers": barriers,
        "chain": chain,
    }

