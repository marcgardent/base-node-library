"""The comments of a text, kept in the tree: on the nodes they go with.

Each comment goes with a statement or a block of the text:

- alone on its lines, with what follows it: `before` the statement, or the `end` of the block
  whose closing brace comes next;
- after code, with the statement of that line (`after`), or the block it closes (`end_after`);
- before the first `use`, with the file (`file`); after the last graph, below it (`below`);
  above the `// @profile` line, at the head of the text (`head`).

They are kept, as written and `//` included, in a property of what the statement makes: its node,
the frame of a block, the Group Output for the return, the zone's output node for a zone and its
return (`return_before`, `return_after`), the tree for its graph. A statement that makes no node
of its own (`b = a.x`) passes its comments to the next one. The file's comments (`head`, `file`)
go with its last graph, the one a text stands for. `// @profile` lines are left out: Tree → Text
writes its own.

Tree → Text writes them back in the same places, so that a text read back from its tree keeps
its comments, as the formatter places them.
"""

from collections import defaultdict

from ..lang import ast, ir, printer
from ..lang.lexer import tokenize
from ..lang.parser import parse

KEY = "base_node_comment"

OPEN = ("before", "after")
CLOSE = ("end", "end_after")


def is_profile(text):
    return text.lstrip("/").strip().startswith("@profile")


# Text -> tree


class Event:
    """A place comments go with: a statement or block opening (`open`), a block closing (`close`),
    a `use` line, the `// @profile` line. `target` is (AST object, slot prefix, AST graph)."""

    def __init__(self, line, kind, target):
        self.line, self.kind, self.target = line, kind, target
        self.notes = defaultdict(list)  # slot -> comment texts


def events(file):
    """The places of the text, in its order."""
    out = [Event(u.line, "use", None) for u in sorted(file.uses, key=lambda u: u.line)]

    def walk(body, g, zone):
        for s in body:
            if isinstance(s, ast.Frame):
                out.append(Event(s.line, "open", (s, "", g)))
                walk(s.body, g, zone)
                out.append(Event(s.end, "close", (s, "", g)))
            elif isinstance(s, ast.Assign) and isinstance(s.value, ast.ZONES):
                out.append(Event(s.line, "open", (s, "", g)))
                walk(s.value.body, g, s)
                out.append(Event(s.value.end, "close", (s, "", g)))
            elif isinstance(s, ast.Return) and zone is not None:
                out.append(Event(s.line, "open", (zone, "return_", g)))
            else:
                out.append(Event(s.line, "open", (s, "", g)))

    for g in file.graphs:
        out.append(Event(g.line, "open", (g, "", g)))
        walk(g.body, g, None)
        out.append(Event(g.end, "close", (g, "", g)))
    return out


FILE_SLOTS = {"use": "file", "profile": "head"}


def collect(source, filename="<text>"):
    """The places of the text, each with the comments that go with it."""
    file = parse(source, filename)
    rows = source.split("\n")
    places = events(file)
    found = [c for c in tokenize(source, filename, strict=False) if c.kind == "COMMENT"]
    profile = next((c for c in found if is_profile(c.text)), None)
    if profile is not None and all(e.line > profile.line for e in places):
        places.insert(0, Event(profile.line, "profile", None))
    for c in found:
        if is_profile(c.text):
            continue
        text = c.text.rstrip()
        alone = not rows[c.line - 1][:c.col - 1].strip()
        if alone:
            e = next((e for e in places if e.line > c.line), None)
            if e is None:
                places[-1].notes["below"].append(text)  # the last graph's closing brace
            else:
                e.notes[FILE_SLOTS.get(e.kind) or ("before" if e.kind == "open" else "end")].append(text)
            continue
        on = [e for e in places if e.line == c.line]
        e = next((e for e in on if e.kind == "open"), on[0] if on else None)
        if e is None:
            # Within a statement written on several lines: with the last place before it
            e = next(e for e in reversed(places) if e.line < c.line)
        e.notes[FILE_SLOTS.get(e.kind) or ("after" if e.kind == "open" else "end_after")].append(text)
    return places


def keep(source, filename, graphs, built, made):
    """Write the comments of `source` into the trees built from it.

    `graphs` are its ir graphs, `built` their trees by name, `made` by graph name the
    (nodes, frames) the builder made: ir id -> Blender node.
    """
    by_name = {g.name: g for g in graphs if g.module is None}
    own = [built[name] for name in by_name]
    for tree in own:
        tree.pop(KEY, None)
    places = collect(source, filename)
    notes = defaultdict(lambda: defaultdict(list))  # (id, holder) -> slot -> texts
    holders = {}
    carried = []
    last = own[-1] if own else None

    for e in places:
        texts = [t for slot in ("head", "file", "before", "after", "end", "end_after", "below")
                 for t in e.notes.get(slot, [])]
        if e.kind in FILE_SLOTS:
            if last is not None:
                notes[id(last)][FILE_SLOTS[e.kind]].extend(texts)
                holders[id(last)] = last
            continue
        obj, prefix, g = e.target
        holder = resolve(obj, by_name.get(g.name), built.get(g.name), made.get(g.name, ({}, {})))
        if holder is None:
            carried.extend(texts)
            continue
        slots = notes[id(holder)]
        holders[id(holder)] = holder
        if carried:
            slots[prefix + ("before" if e.kind == "open" else "end")].extend(carried)
            carried = []
        for slot, found in e.notes.items():
            slots[slot if slot == "below" else prefix + slot].extend(found)
    if carried and last is not None:
        notes[id(last)]["below"].extend(carried)
        holders[id(last)] = last

    for i, slots in notes.items():
        written = {slot: "\n".join(texts) for slot, texts in slots.items() if texts}
        if written:
            holders[i][KEY] = written


def resolve(obj, g, tree, made):
    """The tree or node that holds the comments of an AST object, or None."""
    if g is None or tree is None:
        return None
    nodes, frames = made
    if isinstance(obj, ast.Graph):
        return tree
    if isinstance(obj, ast.Return):
        return nodes.get(ir.GROUP_OUTPUT)
    if isinstance(obj, ast.Frame):
        if obj.continued:
            return None
        f = next((f for f in g.frames if (f.line, f.col) == (obj.line, obj.col)), None)
        return frames.get(f.id) if f is not None else None
    if isinstance(obj, ast.Assign):
        named = [n for n in g.nodes if n.name == obj.name]
        if not named:
            return None
        n = min(named, key=lambda n: (n.line < obj.line, abs(n.line - obj.line)))
        return nodes.get(n.id)
    return None


# Tree -> text


def notes_of(holder):
    found = holder.get(KEY) if holder is not None else None
    if found is None:
        return {}
    found = found.to_dict() if hasattr(found, "to_dict") else dict(found)
    return {k: v.split("\n") for k, v in found.items() if isinstance(v, str) and v}


def write(text, file, holders):
    """`text`, printed from `file`, with the comments of the trees and nodes back in it.

    `holders` maps the id of an AST object of `file` to (tree or node, slot prefix).
    """
    if not holders:
        return text
    parsed = parse(text)
    rows = text.split("\n")
    above = defaultdict(list)  # row -> lines above it
    below = defaultdict(list)  # row -> lines below it
    trail = defaultdict(list)  # row -> comments after its code
    opened = set()  # rows of `"Note" {}` written apart to hold comments

    def pad(row):
        return rows[row][:len(rows[row]) - len(rows[row].lstrip())]

    def place(a, b):
        holder, prefix = holders.get(id(a), (None, ""))
        notes = notes_of(holder)
        if not notes:
            return
        row = b.line - 1
        above[row].extend(pad(row) + t for t in notes.get(prefix + "before", []))
        trail[row].extend(notes.get(prefix + "after", []))
        if prefix:
            return  # the return of a zone: its block is the zone's
        end = b.end if isinstance(b, (ast.Frame, ast.Graph)) else b.value.end \
            if isinstance(b, ast.Assign) and isinstance(b.value, ast.ZONES) else None
        if end is None:
            return
        inside, closing = notes.get("end", []), notes.get("end_after", [])
        if end - 1 == row and (inside or closing) and rows[row].rstrip().endswith("{}"):
            opened.add(row)
            below[row].extend(pad(row) + printer.INDENT + t for t in inside)
            below[row].append("  ".join([pad(row) + "}"] + closing))
        else:
            above[end - 1].extend(pad(end - 1) + printer.INDENT + t for t in inside)
            trail[end - 1].extend(closing)
        if isinstance(b, ast.Graph):
            below[end - 1].extend(notes.get("below", []))

    def walk(sa, sb):
        for a, b in zip(sa, sb):
            place(a, b)
            if isinstance(a, ast.Frame):
                walk(a.body, b.body)
            elif isinstance(a, ast.Assign) and isinstance(a.value, ast.ZONES):
                walk(a.value.body, b.value.body)

    for ga, gb in zip(file.graphs, parsed.graphs):
        place(ga, gb)
        walk(ga.body, gb.body)

    out = []
    for i, row in enumerate(rows):
        out.extend(above[i])
        if i in opened:
            row = row.rstrip()[:-1]
        out.append("  ".join([row] + trail[i]) if trail[i] else row)
        out.extend(below[i])
    return "\n".join(out)
