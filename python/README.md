# base-node

Python reference implementation of Base Node (`.bn`), a text format for node graphs: parser, formatter, profile checker and CLI, with no dependency.

```bn
geometry graph relief(geometry: Geometry, height: Float = 0.4 in 0.0..2.0) -> Geometry {
  h = length(Position()) * height
  return SetPosition(geometry, offset: CombineXYZ(z: h))
}
```

## Install

```bash
pip install "base-node @ git+https://github.com/marcgardent/base-node-library.git#subdirectory=python"
```

## CLI

```bash
base-node fmt file.bn
base-node fmt --check file.bn
base-node check --profile vector2d file.bn
base-node ast file.bn
```

## Library

```python
import base_node as bn

ast = bn.parse(source)
formatted = bn.format_source(source)
errors = bn.check_profile(graphs, profile="vector2d")
```

The language, the profiles, the standard library and the Blender extension are described in the repository: <https://github.com/marcgardent/base-node-library>.

License: MIT OR Apache-2.0.
