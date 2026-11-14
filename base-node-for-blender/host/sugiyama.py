"""Layered placement of node boxes: links go left to right and line up with their sockets.

A simplified port of Node Arrange by Leonardo Pike-Excell
(https://github.com/Leonardo-Pike-Excell/node-arrange, GPL-2.0-or-later), without networkx
and without reading Blender's memory:

- ranks: longest path from the sources, then each node pulled next to its first user
  (Node Arrange runs network simplex);
- order of each column: barycenters of the sockets, swept both ways, the fewest crossings kept;
- y: Brandes–Köpf, four alignments balanced, with the sockets of a block on one line;
- x: one column per rank, wider gaps where links are steep;
- frames: each one placed inside out as a block of its own (Node Arrange threads clusters
  through the whole graph); no reroute is added nor removed.

No bpy here: the host turns a tree into boxes, and the places back into locations.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import pairwise
from math import ceil, floor, inf
from statistics import fmean


@dataclass(eq=False)
class Box:
    """A node: its size, the y of each socket under its top, its frame, its place now (top-left, y up)."""

    id: object
    width: float
    height: float
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    frame: object = None
    x: float = 0.0
    y: float = 0.0


@dataclass(eq=False)
class Frame:
    id: object
    parent: object = None
    label: float = 0.0  # room of the title over the content


def arrange(boxes, links, frames=(), spacing=(50, 50), padding=30, iterations=24):
    """{box id: (x, y)}, the top-left corner of each box, y up, the layout's top-left at the origin.

    `links` are (from box id, output index, to box id, input index); a link to a box not in
    `boxes` is left out. Each frame holds its boxes and frames in a block of its own,
    `padding` around them and its title on top.
    """
    by_id = {b.id: b for b in boxes}
    fr = {f.id: f for f in frames}

    def frame_of(b):
        return b.frame if b.frame in fr else None

    def up(f):
        p = fr[f].parent
        return p if p in fr else None

    def path(b):
        """The frames around a box, innermost first."""
        out, f = [], frame_of(b)
        while f is not None and f not in out:
            out.append(f)
            f = up(f)
        return out

    paths = {b.id: path(b) for b in boxes}

    def child_of(bid, level):
        """The element of `level` (a frame, None for the root) that holds box `bid`, or None."""
        p = paths[bid]
        if (p[0] if p else None) == level:
            return ("box", bid)
        for k, f in enumerate(p):
            if (p[k + 1] if k + 1 < len(p) else None) == level:
                return ("frame", f)
        return None

    def depth(f):
        d = 0
        while (f := up(f)) is not None:
            d += 1
        return d

    used = {f for p in paths.values() for f in p}
    placed = {}  # frame id -> (width, height, {box id: (dx, dy down)})

    for level in sorted(used, key=depth, reverse=True) + [None]:
        keys = [("box", b.id) for b in boxes if frame_of(b) == level]
        keys += [("frame", f) for f in used if up(f) == level]
        if not keys:
            continue
        elems = {}
        for k in keys:
            if k[0] == "box":
                b = by_id[k[1]]
                elems[k] = _V(b.width, b.height, b.x, b.y)
            else:
                w, h, inner = placed[k[1]]
                xs = [by_id[i].x for i in inner]
                ys = [by_id[i].y for i in inner]
                elems[k] = _V(w, h, min(xs), max(ys))

        def offset(bid, key):
            return placed[key[1]][2][bid][1] if key[0] == "frame" else 0.0

        edges = []
        for a, i, b, j in links:
            if a not in by_id or b not in by_id:
                continue
            ka, kb = child_of(a, level), child_of(b, level)
            if ka is None or kb is None or ka == kb:
                continue
            ba, bb = by_id[a], by_id[b]
            oa = offset(a, ka) + (ba.outputs[i] if i < len(ba.outputs) else ba.height / 2)
            ob = offset(b, kb) + (bb.inputs[j] if j < len(bb.inputs) else bb.height / 2)
            edges.append((elems[ka], oa, elems[kb], ob))

        pos = _place(list(elems.values()), edges, spacing, iterations)

        flat = {}
        for k, v in elems.items():
            x, y = pos[v]
            if k[0] == "box":
                flat[k[1]] = (x, y)
            else:
                for bid, (dx, dy) in placed[k[1]][2].items():
                    flat[bid] = (x + dx, y + dy)
        left = min(pos[v][0] for v in elems.values())
        top = min(pos[v][1] for v in elems.values())
        right = max(pos[v][0] + v.width for v in elems.values())
        bottom = max(pos[v][1] + v.height for v in elems.values())
        if level is None:
            return {bid: (x - left, -(y - top)) for bid, (x, y) in flat.items()}
        head = padding + max(0.0, fr[level].label)
        placed[level] = (right - left + 2 * padding, bottom - top + padding + head,
                         {bid: (x - left + padding, y - top + head) for bid, (x, y) in flat.items()})
    return {}


class _V:
    """An element of one level: a box, a frame's block, or a dummy where a long link passes."""

    __slots__ = ("width", "height", "x0", "y0", "dummy", "rank")

    def __init__(self, width, height, x0=0.0, y0=0.0, dummy=False):
        self.width, self.height, self.x0, self.y0, self.dummy = width, height, x0, y0, dummy
        self.rank = 0


def _place(elems, edges, spacing, iterations):
    """{element: (x, y down)} for one level; `edges` are (u, offset at u, v, offset at v)."""
    sx, sy = spacing
    succ = defaultdict(list)
    for e in edges:
        succ[e[0]].append(e)

    # Links that would go back (a cycle through two frames) are left out
    state, dag = {}, []
    for root in sorted(elems, key=lambda v: (v.x0, -v.y0)):
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter(succ[root]))]
        while stack:
            v, it = stack[-1]
            e = next(it, None)
            if e is None:
                state[v] = 2
                stack.pop()
                continue
            w = e[2]
            if state.get(w) == 1:
                continue
            dag.append(e)
            if w not in state:
                state[w] = 1
                stack.append((w, iter(succ[w])))

    preds, succs = defaultdict(list), defaultdict(list)
    for e in dag:
        preds[e[2]].append(e)
        succs[e[0]].append(e)

    # Longest path from the sources, then each node pulled next to its first user
    order, ready = [], [v for v in elems if not preds[v]]
    left = {v: len(preds[v]) for v in elems}
    while ready:
        v = ready.pop()
        order.append(v)
        for e in succs[v]:
            left[e[2]] -= 1
            if not left[e[2]]:
                ready.append(e[2])
    for v in order:
        v.rank = max((e[0].rank + 1 for e in preds[v]), default=0)
    for v in reversed(order):
        if succs[v]:
            v.rank = min(e[2].rank for e in succs[v]) - 1
    # Then each node moves to the side with more links, which shortens them (network simplex
    # in small): a node fed by many sends its one result over the distance instead
    for _ in range(8):
        moved = False
        for v in order:
            n_in, n_out = len(preds[v]), len(succs[v])
            if n_in > n_out:
                to = max(e[0].rank for e in preds[v]) + 1
            elif n_out > n_in:
                to = min(e[2].rank for e in succs[v]) - 1
            else:
                continue
            if to != v.rank:
                v.rank, moved = to, True
        if not moved:
            break
    ranks = {r: i for i, r in enumerate(sorted({v.rank for v in elems}))}
    for v in elems:
        v.rank = ranks[v.rank]

    # A long link passes through one dummy per column; links of one socket share them
    segs = []
    shared = {}
    for u, ou, v, ov in dag:
        a, oa = u, ou
        for r in range(u.rank + 1, v.rank):
            key = (u, ou, r)
            if key not in shared:
                d = _V(0.0, 0.0, u.x0, u.y0 - ou, dummy=True)
                d.rank = r
                shared[key] = d
                segs.append((a, oa, d, 0.0))
            a, oa = shared[key], 0.0
        segs.append((a, oa, v, ov))
    segs = list({(id(s[0]), s[1], id(s[2]), s[3]): s for s in segs}.values())
    nodes = list(elems) + list(shared.values())

    columns = [[] for _ in range(len(ranks))]
    for v in nodes:
        columns[v.rank].append(v)
    for col in columns:
        col.sort(key=lambda v: (-v.y0, v.x0))

    ins, outs = defaultdict(list), defaultdict(list)
    for s in segs:
        outs[s[0]].append(s)
        ins[s[2]].append(s)

    def gap(a, b):
        return sy / 2 if a.dummy or b.dummy else sy

    _order(columns, ins, outs, gap, iterations)
    ys = _vertical(columns, ins, outs, gap)
    # The balance takes each element from its own pair of alignments: push down what overlaps
    for col in columns:
        for a, b in pairwise(col):
            ys[b] = max(ys[b], ys[a] + a.height + gap(a, b))

    pos = {}
    x = 0.0
    for col in columns:
        width = max((v.width for v in col), default=0.0)
        for v in col:
            pos[v] = (x + (width - v.width) / 2, ys[v])
        steep = sum(1 for v in col for u, ou, w, ow in outs[v]
                    if abs(ys[w] + ow - ys[u] - ou) >= 3 * sx)
        x += width + (1 + min(steep / 4, 2)) * sx
    return {v: pos[v] for v in elems}


# Crossings ----------------------------------------------------------------------------------


def _tops(col, gap):
    top, out = 0.0, {}
    for i, v in enumerate(col):
        out[v] = top
        top += v.height + (gap(v, col[i + 1]) if i + 1 < len(col) else 0)
    return out


def _crossings(columns, outs):
    total = 0
    for col, nxt in pairwise(columns):
        at = {v: i for i, v in enumerate(nxt)}
        here = {v: i for i, v in enumerate(col)}
        ends = sorted(((here[u], ou), (at[w], ow)) for v in col for u, ou, w, ow in outs[v])
        # Pairs ordered at the left and reversed at the right
        for i, (a, b) in enumerate(ends):
            for c, d in ends[i + 1:]:
                if c > a and d < b:
                    total += 1
    return total


def _order(columns, ins, outs, gap, iterations):
    """Reorder each column by the barycenter of its links' sockets; keep the fewest crossings."""
    best = [list(c) for c in columns]
    fewest = _crossings(columns, outs)
    for it in range(iterations):
        if not fewest:
            break
        rightwards = it % 2 == 0
        seq = range(1, len(columns)) if rightwards else range(len(columns) - 2, -1, -1)
        for c in seq:
            fixed = _tops(columns[c - 1] if rightwards else columns[c + 1], gap)
            here = _tops(columns[c], gap)

            def key(v):
                if rightwards:
                    ends = [fixed[u] + ou - ov for u, ou, _, ov in ins[v]]
                else:
                    ends = [fixed[w] + ow - ou for _, ou, w, ow in outs[v]]
                return fmean(ends) if ends else here[v]

            columns[c].sort(key=key)
        n = _crossings(columns, outs)
        if n < fewest:
            fewest, best = n, [list(c) for c in columns]
    columns[:] = best


# Brandes–Köpf -------------------------------------------------------------------------------
# http://dx.doi.org/10.1007/3-540-45848-4_3, with the shifts of https://arxiv.org/abs/2008.01252


def _vertical(columns, ins, outs, gap):
    """{element: its top, y down}: the mean of the two middle of four alignments."""
    layouts = []
    for rightwards in (True, False):
        cols = columns if rightwards else columns[::-1]
        if rightwards:
            upper = {v: [(u, ou, ov) for u, ou, _, ov in ins[v]] for c in cols for v in c}
        else:
            upper = {v: [(w, ow, ou) for _, ou, w, ow in outs[v]] for c in cols for v in c}
        for downwards in (True, False):
            if downwards:
                tops = _bk([list(c) for c in cols], upper, gap)
                layouts.append((tops, True))
            else:
                # Upside down: the columns reversed and each offset taken from the bottom
                flip = {v: [(u, u.height - ou, v.height - ov) for u, ou, ov in ups]
                        for v, ups in upper.items()}
                tops = _bk([c[::-1] for c in cols], flip, gap)
                layouts.append(({v: -(t + v.height) for v, t in tops.items()}, False))

    def span(t):
        return max(y + v.height for v, y in t.items()) - min(t.values())

    smallest = min((t for t, _ in layouts), key=span)
    low, high = min(smallest.values()), max(y + v.height for v, y in smallest.items())
    aligned = []
    for t, downwards in layouts:
        if downwards:
            move = low - min(t.values())
        else:
            move = high - max(y + v.height for v, y in t.items())
        aligned.append({v: y + move for v, y in t.items()})
    return {v: fmean(sorted(t[v] for t in aligned)[1:3]) for v in smallest}


def _bk(cols, upper, gap):
    """Tops (y down) packed upwards: each element aligned with its median upper neighbor."""
    index = {v: i for c in cols for i, v in enumerate(c)}
    col_of = {v: c for c in cols for v in c}

    def inner(v):
        return v.dummy and any(u.dummy for u, _, _ in upper[v])

    # Type 1 conflicts: a segment crossing a run of dummies gives way to it
    marked = set()
    for prev, col in pairwise(cols):
        k0, l = 0, 0
        for l1, v in enumerate(col):
            if inner(v):
                k1 = index[next(u for u, _, _ in upper[v] if u.dummy)]
            elif l1 == len(col) - 1:
                k1 = len(prev) - 1
            else:
                continue
            while l <= l1:
                w = col[l]
                l += 1
                if inner(w):
                    continue
                for u, _, _ in upper[w]:
                    if index[u] < k0 or index[u] > k1:
                        marked.add((u, w))
            k0 = k1

    root = {v: v for v in index}
    align = {v: v for v in index}
    for col in cols:
        r = -1
        for v in col:
            ups = sorted({u for u, _, _ in upper[v]}, key=index.get)
            if not ups:
                continue
            m = (len(ups) - 1) / 2
            for u in ups[floor(m):ceil(m) + 1]:
                if align[v] is v and (u, v) not in marked and r < index[u]:
                    align[u] = v
                    root[v] = root[u]
                    align[v] = root[v]
                    r = index[u]

    def block(start):
        yield start
        w = start
        while (w := align[w]) is not start:
            yield w

    # Inside a block, each element moves so that its sockets meet those of the one before
    shift_in = {}
    for v in index:
        if root[v] is not v:
            continue
        shift_in[v] = 0.0
        for a, b in pairwise(block(v)):
            ends = [shift_in[a] + ou - ov for u, ou, ov in upper[b] if u is a]
            shift_in[b] = fmean(ends) if ends else shift_in[a]

    y, sink, shift = {}, {v: v for v in index}, {v: inf for v in index}

    def place(v):
        if v in y:
            return
        y[v] = 0.0
        first = True
        for w in block(v):
            i = index[w]
            if i == 0:
                continue
            n = col_of[w][i - 1]
            u = root[n]
            place(u)
            if sink[v] is v:
                sink[v] = sink[u]
            if sink[v] is sink[u]:
                s = y[u] + shift_in[n] - shift_in[w] + n.height + gap(n, w)
                y[v] = s if first else max(y[v], s)
                first = False
        for w in block(v):
            y[w] = y[v]
            sink[w] = sink[v]

    for v in index:
        if root[v] is v:
            place(v)

    touching = defaultdict(set)
    for col in cols:
        for lower, higher in pairwise(reversed(col)):
            if sink[higher] is not sink[lower]:
                touching[id(col_of[sink[lower]])].add((higher, lower))
    for col in cols:
        if shift[sink[col[0]]] == inf:
            shift[sink[col[0]]] = 0.0
        for u, v in touching[id(col)]:
            s = y[v] + shift_in[v] - y[u] - shift_in[u] - u.height - gap(u, v)
            shift[sink[u]] = min(shift[sink[u]], shift[sink[v]] + s)

    return {v: y[v] + (0.0 if shift[sink[v]] == inf else shift[sink[v]]) + shift_in[v] for v in index}
