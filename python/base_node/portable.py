"""Portable subset of the .bn language and alias contract.

Defines the portable subset of .bn shared across host runtimes:
- Canonical portable types;
- Portable implicit inputs;
- Alias contract (portable name / host name);
- Core 2D portable nodes;
- Validation via check_portable(graphs);
- Schema export via dump_portable_schema(schema).
"""

import math
from typing import Any

# Canonical portable types
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

# Portable implicit inputs
PORTABLE_IMPLICIT = ("Position", "Normal", "Index", "ID")

# Corresponding internal interface socket identifiers in Blender
PORTABLE_IMPLICIT_IDENTIFIERS = {"POSITION", "NORMAL", "INDEX", "ID_OR_INDEX"}

# Alias contract between canonical portable name and Blender (host) name
PORTABLE_ALIASES = {
    "WhiteNoise": "TexWhiteNoise",
    "TransformGeometry": "Transform",
    "CurveCircle": "CurvePrimitiveCircle",
    "CurveQuadrilateral": "CurvePrimitiveQuadrilateral",
    "CurveLine": "CurvePrimitiveLine",
    "BoundingBox": "BoundBox",
}

# Reverse aliases: Blender name -> canonical portable name
BLENDER_TO_PORTABLE_ALIASES = {v: k for k, v in PORTABLE_ALIASES.items()}

# Tree kinds accepted in the portable subset
PORTABLE_KINDS = ("geometry", "vector", "pixel")

# Core 2D common nodes (canonical portable names)
CANONICAL_PORTABLE_NODES = (
    # Math / vector computation, logic
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
    # 2D Curves
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
    # 2D Mesh & Points
    "MeshGrid",
    "MeshCircle",
    "MeshLine",
    "Points",
    "Triangulate",
    # General 2D Geometry
    "SetPosition",
    "TransformGeometry",
    "JoinGeometry",
    "InstanceOnPoints",
    "RealizeInstances",
    "MergeByDistance",
    "BoundingBox",
    "SetMaterial",
    "SampleIndex",
    # Attributes & contextual inputs
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

# All recognized text names (canonical + Blender-specific names)
PORTABLE_NODES = tuple(dict.fromkeys(CANONICAL_PORTABLE_NODES + tuple(PORTABLE_ALIASES.values())))

# Node class identifiers (bl_idname) allowed in a portable graph
PORTABLE_BL_IDNAMES = {
    # Math & Logic
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
    # 2D Geometry & Curves
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
    # Attributes & Context
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
    # Portable zones (repeat and foreach)
    "GeometryNodeRepeatInput",
    "GeometryNodeRepeatOutput",
    "GeometryNodeForeachGeometryElementInput",
    "GeometryNodeForeachGeometryElementOutput",
    # Group plumbing
    "NodeGroupInput",
    "NodeGroupOutput",
    "GeometryNodeGroup",
    "group_input",
    "group_output",
    "NodeFrame",
    "NodeReroute",
}


def _plain(value: Any) -> Any:
    """Normalize scalar or vector values for JSON."""
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
    """Portable node schema with direct or nested node lookup."""

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
    """Check that compiled ir.Graph objects only use types and nodes
    from the portable contract.

    Returns [] if portable, or a list of error strings.
    """
    errors: list[str] = []
    if not isinstance(graphs, (list, tuple)):
        graphs = [graphs]

    for g in graphs:
        # 1. Tree kind
        if g.kind not in PORTABLE_KINDS:
            errors.append(
                f"Graph '{g.name}': tree kind '{g.kind}' is not portable (expected {PORTABLE_KINDS})"
            )

        # 2. Interface input / output types
        for name, typ in g.inputs:
            if typ not in PORTABLE_TYPES:
                errors.append(
                    f"Graph '{g.name}': input '{name}' has non-portable type '{typ}'"
                )
        for name, typ in g.outputs:
            if typ not in PORTABLE_TYPES:
                errors.append(
                    f"Graph '{g.name}': output '{name}' has non-portable type '{typ}'"
                )

        # 3. Implicit inputs
        for param, defs in g.defaults.items():
            if "implicit" in defs:
                impl = defs["implicit"]
                if (
                    impl not in PORTABLE_IMPLICIT
                    and impl not in PORTABLE_IMPLICIT_IDENTIFIERS
                ):
                    errors.append(
                        f"Graph '{g.name}': implicit input '{impl}' for '{param}' is not portable"
                    )

        # 4. Nodes and zones
        for node in g.nodes:
            if node.bl_idname not in PORTABLE_BL_IDNAMES:
                errors.append(
                    f"Graph '{g.name}': node '{node.name or node.bl_idname}' "
                    f"(bl_idname '{node.bl_idname}') outside portable contract"
                )

            # Check item types (zones, capture attribute, etc.)
            if node.items:
                for item_name, item_type in node.items:
                    if item_type not in PORTABLE_TYPES:
                        errors.append(
                            f"Graph '{g.name}': item '{item_name}' of node '{node.bl_idname}' "
                            f"has non-portable type '{item_type}'"
                        )
            if node.out_items:
                for item_name, item_type in node.out_items:
                    if item_type not in PORTABLE_TYPES:
                        errors.append(
                            f"Graph '{g.name}': item output '{item_name}' of node '{node.bl_idname}' "
                            f"has non-portable type '{item_type}'"
                        )

    return errors


def dump_portable_schema(schema: Any) -> PortableSchema:
    """Extract properties (props) and default socket signatures (inputs, outputs) for each portable node."""
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

        # If Blender name differs, also reference the entry by its Blender name
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
