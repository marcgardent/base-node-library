# base-node-library

Text format (`.bn`) for node graphs. Reads and writes node trees as functions.

```bn
use math (bump)

geometry graph relief(geometry: Geometry, height: Float = 0.4 in 0.0..2.0) -> Geometry {
  "Displaces vertices along Z using a radial bump"
  h = bump(length(Position()) / 3.0, 0.5, 0.2) * height
  return SetPosition(geometry, offset: CombineXYZ(z: h))
}
```

| [`examples/chrono_hud.bn`](examples/chrono_hud.bn) | [`examples/living_diorama.bn`](examples/living_diorama.bn) | [`examples/metaball_symphony.bn`](examples/metaball_symphony.bn) |
|---|---|---|
| ![chrono-hud](site/images/showcase-chrono-hud.gif) | ![living-diorama](site/images/showcase-living-diorama.gif) | ![metaball-symphony](site/images/showcase-metaball-symphony.gif) |

| `stdlib/sdf2d.bn` | `stdlib/curves2d.bn` |
|---|---|
| ![sdf2d](site/images/sdf2d.png) | ![curves2d](site/images/curves2d.png) |
| **`stdlib/patterns2d.bn`** | **`stdlib/math.bn`** |
| ![patterns2d](site/images/patterns2d.png) | ![math-sdf](site/images/math-sdf.png) |

## Layout

| Path | Description | License |
|---|---|---|
| [`spec/reference.md`](spec/reference.md) | `.bn` grammar and semantics | MIT OR Apache-2.0 |
| [`spec/versioning.md`](spec/versioning.md) | Language editions, stdlib, profiles, and SemVer lifecycle | MIT OR Apache-2.0 |
| [`profiles/`](profiles/) | Target profiles (`core`, `sdf2d`, `vector2d`, `ink2d`, `raster2d`, `blender-geometry`) | MIT OR Apache-2.0 |
| [`stdlib/`](stdlib/) | Standard `.bn` modules and manifest (`math`, `sdf2d`, `curves2d`, `patterns2d`, `ink2d`) | MIT OR Apache-2.0 |
| [`conformance/`](conformance/) | Shared `.bn` test corpus and expected ASTs | MIT OR Apache-2.0 |
| [`python/`](python/) | Zero-dependency Python parser, formatter, and CLI (`base_node`) | MIT OR Apache-2.0 |
| [`rust/`](rust/) | `wasm32`-compatible Rust parser, formatter, and profile checker (`base-node`) | MIT OR Apache-2.0 |
| [`base-node-for-blender/`](base-node-for-blender/) | Blender 5.2+ extension *Base Node* (node tree ⇄ `.bn` text, stdlib bundled) | GPL-3.0-or-later |

## Profiles

Each profile extends its parent and restricts allowed types, implicit inputs, zones, and nodes:

```text
core              Scalar/vector math, logic, noise, repeat (math.bn)
 └─ sdf2d         + 2D spatial context: Position, Normal, Index, ID (sdf2d.bn)
     ├─ vector2d  + Geometry, 2D curves/meshes/points/instances, foreach (curves2d.bn, patterns2d.bn)
     │   └─ ink2d + Living ink, GP3 strokes, dynamics, tilt, draw_time (ink2d.bn)
     │       └─ blender-geometry  + Full Blender 5.2+ Geometry Nodes (3D, volumes, closures, bundles)
     └─ raster2d  + Image buffers, blend modes, filters, rasterize/vectorize
```

## Python (`python/`)

Install from GitHub or a local checkout:

```bash
# From GitHub (pip / uv)
pip install "base-node @ git+https://github.com/marcgardent/base-node-library.git#subdirectory=python"

# From a local clone
pip install -e ./python
```

Or in `pyproject.toml`:

```toml
dependencies = [
  "base-node @ git+https://github.com/marcgardent/base-node-library.git#subdirectory=python",
]
```

CLI:

```bash
base-node fmt file.bn
base-node fmt --check file.bn
base-node check --profile vector2d stdlib/curves2d.bn
base-node ast file.bn
```

Library API:

```python
import base_node as bn

ast = bn.parse(source)
formatted = bn.format_source(source)
errors = bn.check_profile(graphs, profile="vector2d")
```

Run tests:

```bash
PYTHONPATH=python pytest python/tests
```

## Rust (`rust/`)

Add to `Cargo.toml` (Cargo discovers `rust/Cargo.toml` in the repository automatically):

```toml
[dependencies]
# From GitHub
base-node = { git = "https://github.com/marcgardent/base-node-library.git", branch = "main" }

# Or from a local checkout
# base-node = { path = "../base-node-library/rust" }
```

Or via `cargo add`:

```bash
cargo add --git https://github.com/marcgardent/base-node-library.git base-node
```

Library API:

```rust
use base_node::{check_profile, format_source, parse, ProfileKind};

let file = parse(src, "example.bn")?;
let formatted = format_source(src, "example.bn")?;
let errors = check_profile(&file, ProfileKind::Vector2d);
```

Run tests and check WebAssembly target:

```bash
cd rust
cargo test
cargo check --target wasm32-unknown-unknown
```

## Blender Extension (`base-node-for-blender/`)

Add-on for Blender 5.2+ (`id = "base_node"`). The node tree is the only data: its `.bn` text is a temporary view of it.

| Action | Where | Shortcut |
|---|---|---|
| Show the edited tree as `.bn` text, in the same area (inside a group, `Ctrl+Tab` first leaves it, as in Blender) | Node Editor, sidebar *Text > Edit as Text* | `Ctrl+Tab` |
| Write the text into the tree and return to the nodes (the text is removed) | Text Editor, sidebar *Nodes > Back to Nodes* | `Ctrl+Tab` |
| Write the text into the tree and keep editing | Text Editor, *Apply to Tree* | `Ctrl+P` |
| Rewrite the text in the canonical layout, keeping its comments | Text Editor, sidebar *Format* | `Ctrl+Shift+A` |
| Suggestions | Text Editor | `Alt+Space` (set in the preferences) |
| Build the graphs of one or more `.bn` files | *File > Import > Base Node (.bn)* | |
| Arrange the selected nodes (all of them if none is): links left to right, in line with their sockets, frames kept together | Node Editor, *Node > Arrange Nodes*, sidebar *Text* | `Ctrl+Shift+A` |

An unchanged text leaves the tree as it is, node layout included; a text with errors stays open with its diagnostics until it builds.

A `use name` without `from` finds its module in this order: the text `name.bn` of the .blend, `name.bn` next to the imported file, `name.bn` in the *Module Folder* of the add-on preferences, then the standard library bundled with the add-on (a copy of `stdlib/`, kept identical by a test).

Build the package and install it in a local Blender:

```bash
blender --command extension build --source-dir base-node-for-blender --output-dir dist
```

```bash
blender --command extension install-file -r user_default -e dist/base_node-0.9.0.zip
```

Run headless Blender tests:

```bash
blender --background --factory-startup --python-exit-code 1 \
  --python base-node-for-blender/tests/test_extension.py
```

## License

- `spec/`, `profiles/`, `stdlib/`, `conformance/`, `python/`, `rust/`: [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE).
- `base-node-for-blender/`: GPL-3.0-or-later.
- `base-node-for-blender/tests/fixtures/everyday_geometry_nodes.blend`: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/), node groups by Cartesian Caramel, from [blender-remote-asset-library-test-v1](https://github.com/cartesiancaramel/blender-remote-asset-library-test-v1) and its `.bn` text in `everyday_geometry_nodes/` (see [their README](base-node-for-blender/tests/fixtures/README.md)).
