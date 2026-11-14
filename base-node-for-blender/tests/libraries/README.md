# Third-party libraries: non-regression

Each `<name>.toml` names a Geometry Nodes library made by someone else; `test_libraries.py` reads every
Geometry Nodes group of it as `.bn` text, builds it back, reads it again and evaluates it beside the original.
What happens to each group is kept in `<name>.baseline.json`; the test fails when it changes, for better or worse.

| Library | Version | Author | License | Groups |
|---|---|---|---|---|
| [Molecular Nodes](https://github.com/BradyAJohnston/MolecularNodes) | v520.2.0 | Brady Johnston and contributors | GPL-3.0-or-later | see `molecularnodes.baseline.json` |
| [Bioxel Nodes](https://github.com/OmooLab/BioxelNodes) | v2.0.4 | OmooLab | GPL-3.0-or-later | see `bioxelnodes.baseline.json` |
| [H-Style RBD Nodes](https://github.com/excifroge/H-Style-RBD-Nodes) | d9a22d0 (1.0.2) | Excifroge | GPL-3.0-or-later | see `hstylerbd.baseline.json`, `hstylerbd_bricks.baseline.json` |
| [OpenVAT](https://github.com/sharpen3d/openvat) | 43b5196 (1.1.2) | Luke Stilson | GPL-3.0-or-later | see `openvat.baseline.json` |

The `.blend` files are not in this repository: each is fetched once at its fixed version, checked by its
`sha256` and kept in the cache (`$BASE_NODE_CACHE`, `~/.cache/base-node` by default). A library under a license
that lets it be copied here can also name a committed file with `file = "…"` instead of `url`.

## Manifest

```toml
name = "Molecular Nodes"
author = "Brady Johnston and contributors"
homepage = "https://github.com/BradyAJohnston/MolecularNodes"
license = "GPL-3.0-or-later"
version = "v520.2.0"
url = "https://github.com/…/molecularnodes-520.2.0-macos_arm64.zip"   # a .blend, or a .zip with…
member = "assets/nodes.blend"                                          # …the .blend inside it
sha256 = "905e…"                                                       # of the .blend
```

A group whose original does not give twice the same geometry in a kind of evaluation of the test (a sample on
overlapping UVs, say) names that kind in the manifest, which is then not compared for it:

```toml
[nondeterministic]
"UV Deform" = ["mesh caller fed"]   # kinds: "mesh", "curves", "mesh caller", "mesh caller fed"
```

A `.blend` inside a `.zip` is read by HTTP ranges: only the zip's directory and that file are downloaded.

## Baseline

For each group: `status` (`ok`, `export_error`, `build_error`, `unstable`: the rebuilt group does not read back
as the same text, `evaluates_otherwise`: it evaluates otherwise than the original, `on` saying where), the first
`error` line, the kinds of `warnings` and a hash of its `text`.

```bash
blender --background --factory-startup --python-exit-code 1 \
  --python base-node-for-blender/tests/test_libraries.py -- molecularnodes
```

When a change is wanted (a fix, a reader that writes otherwise), write the baselines again and review their diff:

```bash
BASE_NODE_UPDATE_FIXTURES=1 blender --background --factory-startup --python-exit-code 1 \
  --python base-node-for-blender/tests/test_libraries.py
```

The texts of the last run are in the cache under `texts/<name>`, those of the run before under
`texts/<name>.previous`; `diff -r` them to read what a change of the reader changed.

Thanks to the authors of these libraries for publishing them.
