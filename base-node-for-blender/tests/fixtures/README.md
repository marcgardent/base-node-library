# Test fixtures

## `everyday_geometry_nodes.blend`

The 17 Geometry Nodes assets of *Cartesian Caramel's Everyday Nodes*, and the hidden groups they call.

- **Author**: Cartesian Caramel
- **Source**: [cartesiancaramel/blender-remote-asset-library-test-v1](https://github.com/cartesiancaramel/blender-remote-asset-library-test-v1),
  file `5.2 Everyday Geometry Node Assets v5.blend` at commit `6c078f7`
- **License**: [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain)

Only the node groups were kept (the scene and the *Container GN Group* were left out), and the file was saved
compressed with Blender 5.3. The nodes themselves are unchanged.

`test_extension.py` (`test_real_world_assets`) writes each asset as `.bn` text, builds the text back into a
node group, and checks that the text is stable and that the rebuilt group evaluates like the original.

Thanks to Cartesian Caramel for publishing these node groups in the public domain.
