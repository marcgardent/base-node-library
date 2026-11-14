# Base Node (`.bn`) Versioning & Evolution Specification

This document defines the versioning scheme, stability guarantees, and lifecycle management for the Base Node (`.bn`) ecosystem: the language grammar, the standard library (`stdlib/`), the target profiles, and the reference implementations (Python, Rust, Blender extension).

---

## 1. The Four Versioning Tiers

The `.bn` ecosystem separates concerns across four distinct tiers:

```
┌────────────────────────────────────────────────────────┐
│ Tier 1: Language Edition (Syntax & Grammar)            │
│         e.g., Edition 2026                             │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Tier 2: Target Profiles (Hardware & Host Capabilities) │
│         e.g., core@1.0, vector2d@1.0, ink2d@1.0        │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Tier 3: Standard Library Modules (stdlib/)             │
│         e.g., math@0.10.0, ink2d@0.10.0                  │
│         Manifest: stdlib/manifest.json                 │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Tier 4: Toolchain & Reference Packages                 │
│         Python: base-node 0.10.0                        │
│         Rust:   base-node 0.10.0                        │
│         Blender Extension: 0.10.0                       │
└────────────────────────────────────────────────────────┘
```

---

## 2. Tier 1: Language Edition (`edition`)

To balance rapid language innovation with long-term code preservation, `.bn` uses **Language Editions** (inspired by Rust and WGSL epochs):

- **Edition Identifier**: A calendar year string, starting with `"2026"`.
- **Scope**: Lexical tokens, parsing rules, reserved keywords, and AST representation.
- **Backwards Compatibility**: A modern `.bn` compiler supporting Edition `2026` will always parse `2026` source code identically, even when future editions (e.g. `2028`) introduce new keywords or syntactic forms.

### Source Annotation (Pragma)

Source files can optionally declare their target edition in the file header:

```bn
// @edition 2026
```

When omitted, the compiler defaults to the latest stable edition supported by the runtime.

---

## 3. Tier 2: Target Profiles (`profiles/`)

Profiles define what types, implicit sockets, control zones, and node primitives are available on a specific target engine or backend.

Each profile file in `profiles/<name>.json` contains:

```json
{
  "name": "ink2d",
  "version": 1,
  "profile_version": "0.10.0",
  "edition": "2026",
  "description": "2D living ink, Grease Pencil strokes, dynamics, and attributes",
  "extends": "vector2d",
  "types": ["Geometry", "Material"],
  "zones": ["foreach"],
  "nodes": [...]
}
```

- **`version` (Schema Version)**: Integer representing the profile JSON schema version (currently `1`).
- **`profile_version` (SemVer)**: Semantic version of the node catalog for this profile.
- **Hierarchy Guarantee**: Profiles form a strict upward subset lattice:
  $$\text{core} \subset \text{sdf2d} \subset \text{vector2d} \subset \text{ink2d} \subset \text{blender-geometry}$$
  A node tree valid in `vector2d` is guaranteed to be valid in `ink2d` and `blender-geometry`.

---

## 4. Tier 3: Standard Library (`stdlib/`)

The standard library modules provide reusable computational geometry, math, and stylization functions.

### Central Manifest: `stdlib/manifest.json`

The standard library is cataloged in [`stdlib/manifest.json`](file:///home/marcgardent/base-node-library/stdlib/manifest.json), which serves as the single source of truth for standard modules:

```json
{
  "$schema": "./manifest.schema.json",
  "stdlib_version": "0.10.0",
  "edition": "2026",
  "modules": {
    "math": {
      "version": "0.10.0",
      "profile": "core",
      "file": "math.bn",
      "description": "Scalar, vector math, shaping curves, wave functions, and noise"
    },
    "ink2d": {
      "version": "0.10.0",
      "profile": "ink2d",
      "file": "ink2d.bn",
      "dependencies": ["math"],
      "description": "Living ink, organic stroke dynamics, taper, and artistic drawing"
    }
  }
}
```

### Module Header Metadata

Every official `.bn` standard library file must include standardized metadata comments before its `use` imports:

```bn
// Base Node Standard Library — Module ink2d
// @module ink2d
// @version 0.10.0
// @profile ink2d
// @edition 2026

use math (bump, fbm)
...
```

- `@module`: Canonical module identifier (matches filename without `.bn`).
- `@version`: Module SemVer version string.
- `@profile`: Minimal profile required to compile this module.
- `@edition`: Target language edition.

---

## 5. Lifecycle & Stability Policy (Pre-LTS vs LTS)

### Phase 1: Pre-LTS (`0.x.y`) — Active Rapid Iteration
- **Current status**: Version `0.10.0`.
- **Policy**: **No backwards compatibility guarantee prior to LTS 1.0**.
  - Breaking changes to node names, signatures, or module structure may occur between minor versions (`0.7` $\to$ `0.8`).
  - No deprecated alias shims or legacy wrappers are retained in the repository (`stdlib/gp_tools2d.bn` was purged).
  - Canonical naming (`ink2d::`) is enforced strictly.

### Phase 2: Long-Term Support (`1.0.0 LTS`)
- Triggered when the language grammar, profiles, and core stdlib achieve stability across Blender and external backends.
- **Strict Semantic Versioning (SemVer 2.0.0)**:
  - **`MAJOR`**: Breaking changes to the language grammar or removal of stdlib public API functions.
  - **`MINOR`**: Backward-compatible addition of new functions, optional parameters with defaults, or new target profiles.
  - **`PATCH`**: Numerical fixes, algorithmic optimizations, documentation updates.
- **Deprecation Cycle**: Functions planned for removal must remain deprecated for at least one minor release cycle (`@deprecated` attribute / warning in linter).

---

## 6. Tier 4: Toolchain & Implementation Synchronicity

All tools and packages maintained within the repository share a synchronized version number:

| Component | Path | Version Scheme |
|---|---|---|
| Python reference package | [`python/pyproject.toml`](file:///home/marcgardent/base-node-library/python/pyproject.toml) | SemVer (`0.10.0`) |
| Rust WASM crate | [`rust/Cargo.toml`](file:///home/marcgardent/base-node-library/rust/Cargo.toml) | SemVer (`0.10.0`) |
| Blender Extension | [`base-node-for-blender/blender_manifest.toml`](file:///home/marcgardent/base-node-library/base-node-for-blender/blender_manifest.toml) | SemVer (`0.10.0`) |
| Extension Repository Index | [`site/extensions/index.json`](file:///home/marcgardent/base-node-library/site/extensions/index.json) | SemVer (`0.10.0`) |

### CLI Version Reporting

Running `base-node --version` reports:
```text
base-node 0.10.0 (Language Edition 2026, Stdlib 0.10.0)
```
