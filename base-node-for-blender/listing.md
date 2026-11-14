<!--
Description for the extensions.blender.org page (paste below the line into the submission form).
Not part of the extension package: excluded by blender_manifest.toml.
-->

Base Node writes and reads Geometry Nodes trees as text. A tree becomes a `.bn` file of small functions; the file becomes a tree again. Edit nodes as code, review them in diffs, share them as plain text.

## Nodes ⇄ Text in the same area

- **Alt+Z** in the Node Editor shows the edited tree as `.bn` text, in the same area. Press it again to write the text back into the tree and return to the nodes.
- **Alt+P** applies the text to the tree without leaving the text.
- The tree stays the only data: the text is a temporary view, removed when you go back to the nodes. An unchanged text leaves the tree and its layout untouched; a text with errors stays open with its diagnostics until it builds.
- **Ctrl+Shift+A** arranges the selected nodes, or the whole tree: links go left to right, in line with their sockets, and each frame keeps its nodes together. It works in every node editor.

## Writing `.bn`

- Suggestions for nodes, sockets and the graphs of used modules: **Ctrl+Space**, the developers' standard. In `.bn` texts only, it takes the place of Blender's *Maximize Area*: **Ctrl+Alt+Space** still shows the area full screen. Alt+Space or Shift+Space can be chosen instead in the preferences. Optionally, suggestions open by themselves after `(`, `.` and `:`.
- Syntax highlighting, with modes that tell the standard library from your own graphs, or point out nodes that are not portable to a chosen target profile.
- The pipe `|>` is shown as one symbol, ▷, except on the lines you are editing (can be turned off in the preferences). The text keeps `|>`.
- **Format** (**Ctrl+Shift+A**) rewrites a text in the canonical layout, keeping its comments.
- Errors are listed in the sidebar; a click puts the cursor on the line.

## Modules and standard library

- `use math` reuses graphs from another `.bn` file, as node groups.
- The standard library is bundled: `math`, `sdf2d`, `curves2d`, `patterns2d`, `planar2d`, `fillet2d`, `hachures2d`, `deform2d` and `ink2d` (2D ink for Grease Pencil).
- A `use` looks in the texts of the .blend, next to the imported file, in a *Module Folder* you choose, then in the bundled standard library.

## Import

- **File > Import > Base Node (.bn)** builds the graphs of one or more `.bn` files.
- **Add as Modifier** puts a built tree on the active object.

## Permissions

- **Files**: reads the `.bn` files you import, and the modules they use, from disk. Nothing is written outside the .blend, and nothing is sent over the network.

## Links

- Language reference, examples and the Python/Rust parsers: https://marcgardent.github.io/base-node-library/
- Source and issues: https://github.com/marcgardent/base-node-library
