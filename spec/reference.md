# Base Node (`.bn`) Language Reference

Version 1.0.

## 1. File Structure

A `.bn` file is UTF-8 text containing:

1. Optional `use` imports at the top of the file.
2. One or more `graph` declarations.

`//` starts a line comment. Whitespace and newlines are not significant outside literals; a statement ends when the next token cannot continue the current expression.

```bn
use maths (bosse)

geometry graph relief(geometry: Geometry, height: Float = 0.4) -> Geometry {
  "Lifts the center of a mesh"
  h = bosse(length(Position()) / 3.0, 0.5, 0.2) * height
  return SetPosition(geometry, offset: CombineXYZ(z: h))
}
```

## 2. Identifiers and Keywords

- **Identifier**: Unicode letters, digits, and `_`, not starting with a digit (`height`, `fréquence_2`, `p`).
- **Quoted name**: `"Point Count"`. Referenced in expressions by its `snake_case` key (`point_count`), or given an explicit key via `as`: `"Scale" as random_scale: Float`.
- **Reserved words**: `graph`, `return`, `true`, `false`, `and`, `or`, `xor`, `not`, `repeat`, `dot`, `cross`. Host sockets matching a reserved word take a trailing `_` (`not_`).
- **Contextual keywords**: `use`, `from`, `simulate`, `foreach`, `closure`, `_`.
- **Enum values**: Unbound identifiers in argument positions resolve as enum literals (`domain: FACE`, `operation: POWER`).

## 3. Graph Declaration

```bn
[kind][(options)] graph name(inputs...) -> outputs {
  body...
}
```

- **Kind**: `geometry`, `shader`, `compositor`, `vector`, `pixel`.
- **Options**: `geometry(is_tool: true, is_mode_edit: true) graph ...`.
- **Outputs**: Single type `-> Geometry` or named tuple `-> (Mesh: Geometry, Centers: Geometry)`.
- **Docstring**: An optional string literal as the first statement of the body.

### 3.1 Types

| Type | Default | Description |
|---|---|---|
| `Float` | `0.0` | Scalar float |
| `Int` | `0` | Signed integer |
| `Bool` | `false` | Boolean |
| `Vector` | `(0.0, 0.0, 0.0)` | 2D/3D/4D vector |
| `Color` | `(0.0, 0.0, 0.0, 1.0)` | RGBA color (`#rrggbb`, `#rgb`, or tuple) |
| `Rotation` | `(0.0, 0.0, 0.0)` | Euler / quaternion rotation |
| `Matrix` | Identity | 4×4 transform matrix |
| `String` | `""` | UTF-8 string |
| `Menu` | — | Enum selector |
| `Geometry` | — | Mesh, curve, points, instances, or volume |
| `Image` | — | 2D pixel buffer |
| `Material` | — | Material reference |
| `Bundle` | — | Composite socket container |
| `Closure` | — | Deferred subgraph |

### 3.2 Parameters

```bn
name as key: Type(subtype: DISTANCE) = default_value in min..max
```

- `= default_value`: Default literal or implicit input (`Position()`, `Normal()`, `Index()`, `ID()`).
- `in min..max`: Numeric bounds (`in 0.0..1.0`, `in 0.0..`, `in ..1.0`).

### 3.3 Interface Panels

Parameters and outputs can be grouped into nested panels:

```bn
geometry graph scatter(
    geometry: Geometry,
    "Size"(description: "Scale controls") {
      scale: Float = 1.0,
      "Random"(default_closed: true) {
        enable: Bool(is_panel_toggle: true),
        scale as random_scale: Float = 0.2 in 0.0..1.0
      }
    }
) -> Geometry { ... }
```

## 4. Statements

| Syntax | Meaning |
|---|---|
| `x = expr` | Bind expression output |
| `return expr` | Single output return |
| `return (A: e1, B: e2)` | Multi-output return |
| `"Title" #color { ... }` | Visual frame (`#e73` or named color `#teal`) |
| `"Title" .. { ... }` | Continuation of a previously opened frame |
| `"Note" #color {}` | Standalone frame note |

### 4.1 Node Presentation (`@`)

```bn
p = Position() @ hide
h = sin(p.x) @ "Height" #e07030
out = SetPosition(g, offset: o) @ #orange hide mute
```

Flags: `"Label"`, `#color`, `hide` (collapsed), `mute` (bypassed).

## 5. Expressions

- **Node call**: `NodeName(pos_arg, socket: named_arg, PROP: ENUM_VAL)`
- **Output access**: `node.output_name`
- **Vector swizzle**: `v.x`, `v.y`, `v.z`
- **Pipe**: `a |> f(b)` is `f(a, b)`
- **Math operators**: `+`, `-`, `*`, `/`, `<`, `<=`, `>`, `>=`, `==`, `!=`, `and`, `or`, `xor`, `not`
- **Vector products**: `u ⋅ v` (`u dot v`), `u × v` (`u cross v`)
- **Math functions**: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sqrt`, `pow`, `exp`, `log`, `abs`, `min`, `max`, `clamp`, `floor`, `ceil`, `fract`, `mod`, `length`, `normalize`, `distance`

## 6. Control Zones

```bn
// Repeat zone
r = repeat(iterations, val: initial) {
  return (val: val * 0.5)
}

// Foreach element zone
out = foreach(geometry, domain: FACE, p: Position()) {
  return (geometry: Points(position: p))
}

// Closure & Bundle
fn = closure(x: Float) -> (y: Float) {
  return (y: x * 2.0)
}
b = CombineBundle(factor: 0.5, fn: fn)
```

## 7. Compatibility Profiles

| Profile | Extends | Scope |
|---|---|---|
| `core` | — | Scalar/vector math, logic, noise, `repeat` (`maths.bn`) |
| `sdf2d` | `core` | `Position`, `Normal`, `Index`, `ID` (`sdf2d.bn`) |
| `vector2d` | `sdf2d` | `Geometry`, `Material`, 2D curves/meshes/points, `foreach` (`courbes2d.bn`, `motifs2d.bn`) |
| `raster2d` | `sdf2d` | `Image`, blend modes, filters, vectorize/rasterize |
| `blender-geometry` | `vector2d` | Full Blender 5.2+ Geometry Nodes (3D, volumes, `simulate`, `closure`, `Bundle`) |
