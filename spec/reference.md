# Base Node (`.bn`) Language Reference

Language Edition 2026 · Specification Version 0.10.0 (Pre-LTS).  
See [Versioning Specification](versioning.md) for stability policies and release lifecycles.

## 1. File Structure

A `.bn` file is UTF-8 text containing:

1. Optional `use` imports at the top of the file:
   - `use ink2d` imports the module into the `ink2d::` namespace.
   - `use ink2d as gp` imports with an alias namespace (`gp::living_ink(...)`).
   - `use ink2d (living_ink)` imports selected symbols into local scope (`living_ink(...)`).
   - `use math from "//lib/math.bn"` imports from an external or relative file.
   - Without `from`, the host finds the module. Blender looks for the text `math.bn` of the .blend, then `math.bn` next to the imported file, then in the *Module Folder* of the add-on preferences, then in the standard library bundled with the add-on.
2. One or more `graph` declarations.

`//` starts a line comment. Whitespace and newlines are not significant outside literals; a statement ends when the next token cannot continue the current expression.

```bn
use ink2d as gp
use math (bump)

geometry graph relief(geometry: Geometry, height: Float = 0.4) -> Geometry {
  "Lifts the center of a mesh with living ink contour"
  h = bump(length(Position()) / 3.0, 0.5, 0.2) * height
  return geometry |> SetPosition(offset: CombineXYZ(z: h))
                  |> gp::taper_ends()
}
```

## 2. Identifiers and Keywords

- **Identifier**: Unicode letters, digits, and `_`, not starting with a digit (`height`, `frequency_2`, `p`).
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
| `size = 10` | Named constant: an input node of its own (`Value`, `Int`, `Bool`, `Vector`, `Color`, `String`) named `size`; a tuple, a node setting or a menu takes its value |
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

- **Node call**: `NodeName(geometry, socket: value, PROP: ENUM_VAL)`. Inputs are named by their socket's key: the canonical form, the one a tree reads back to, names every input but those a name cannot tell — the geometry the node works on (its first input, linked: the pipe's), the items of a switch (`IndexSwitch(0, a, b)`) and the values of a multi-input, with the inputs before them. A value may still be written by position, in socket order and before the named ones
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

The body of `repeat` sees `iteration`, the body of `simulate` sees `delta_time` and returns `skip`; a state cannot go by these names. A state named like them in Blender takes a key of its own with `as`, used by the body, the return and the users of the zone:

```bn
s = simulate(mesh: geometry, "Delta Time" as dt: 0.0) {
  return (mesh: mesh, dt: dt + delta_time)
}
t = s.dt
```

## 7. Compatibility Profiles

| Profile | Extends | Scope |
|---|---|---|
| `core` | — | Scalar/vector math, logic, noise, `repeat` (`math.bn`) |
| `sdf2d` | `core` | `Position`, `Normal`, `Index`, `ID` (`sdf2d.bn`) |
| `vector2d` | `sdf2d` | `Geometry`, `Material`, 2D curves/meshes/points, `foreach` (`curves2d.bn`, `patterns2d.bn`) |
| `ink2d` | `vector2d` | Living ink, Grease Pencil strokes, dynamics, tilt, draw_time (`ink2d.bn`) |
| `raster2d` | `sdf2d` | `Image`, blend modes, filters, vectorize/rasterize |
| `blender-geometry` | `ink2d` | Full Blender 5.2+ Geometry Nodes (3D, volumes, `simulate`, `closure`, `Bundle`) |
