# Test fixtures

## `everyday_geometry_nodes.blend`

The 17 Geometry Nodes assets of *Cartesian Caramel's Everyday Nodes*, and the hidden groups they call.

- **Author**: Cartesian Caramel
- **Source**: [cartesiancaramel/blender-remote-asset-library-test-v1](https://github.com/cartesiancaramel/blender-remote-asset-library-test-v1),
  file `5.2 Everyday Geometry Node Assets v5.blend` at commit `6c078f7`
- **License**: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain)

Only the node groups were kept (the scene and the *Container GN Group* were left out), and the file was saved
compressed with Blender 5.3. The nodes themselves are unchanged.

## `everyday_geometry_nodes/*.bn`

The same assets as `.bn` text, one file per asset with the hidden groups it calls: what Tree → Text gives for them.
Same author, source and license as the `.blend`.

`test_extension.py` (`test_real_world_assets`) writes each asset as `.bn` text and checks that it is these files,
then builds the text back into a node group and checks that the text is stable and that the rebuilt group
evaluates like the original. When a change of the reader changes the text on purpose, write them again and
review their diff:

```bash
BASE_NODE_UPDATE_FIXTURES=1 blender --background --factory-startup --python-exit-code 1 \
  --python base-node-for-blender/tests/test_extension.py
```

Thanks to Cartesian Caramel for publishing these node groups in the public domain.
