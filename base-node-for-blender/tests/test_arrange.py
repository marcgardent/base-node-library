"""Tests of the node arrangement, without Blender.

    python3 base-node-for-blender/tests/test_arrange.py
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "sugiyama", Path(__file__).resolve().parents[1] / "host" / "sugiyama.py")
sugiyama = importlib.util.module_from_spec(_spec)
sys.modules["sugiyama"] = sugiyama
_spec.loader.exec_module(sugiyama)
Box, Frame, arrange = sugiyama.Box, sugiyama.Frame, sugiyama.arrange


def node(name, n_in, n_out, frame=None, x=0.0, y=0.0):
    rows = n_in + n_out
    return Box(name, 140, 40 + 22 * rows, inputs=[35 + 22 * (n_out + i) for i in range(n_in)],
               outputs=[35 + 22 * i for i in range(n_out)], frame=frame, x=x, y=y)


def rects(boxes, pos):
    return {b.id: (pos[b.id][0], pos[b.id][1], b.width, b.height) for b in boxes}


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay - ah < by and by - bh < ay


def check(boxes, links, frames=()):
    pos = arrange(boxes, links, frames)
    assert set(pos) == {b.id for b in boxes}
    r = rects(boxes, pos)
    ids = list(r)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert not overlaps(r[a], r[b]), f"{a} and {b} overlap: {r[a]} {r[b]}"
    return pos


def test_chain_goes_left_to_right_and_lines_up():
    boxes = [node("in", 0, 1), node("a", 1, 1), node("b", 1, 1), node("out", 1, 0)]
    links = [("in", 0, "a", 0), ("a", 0, "b", 0), ("b", 0, "out", 0)]
    pos = check(boxes, links)
    xs = [pos[n][0] for n in ("in", "a", "b", "out")]
    assert xs == sorted(xs) and len(set(xs)) == 4
    by = {b.id: b for b in boxes}
    # Each link is straight: the output and the input on one line
    for a, i, b, j in links:
        ya = pos[a][1] - by[a].outputs[i]
        yb = pos[b][1] - by[b].inputs[j]
        assert abs(ya - yb) < 1e-6, (a, b, ya, yb)


def test_source_sits_next_to_its_user():
    boxes = [node("in", 0, 1), node("a", 1, 1), node("b", 2, 1), node("c", 0, 1), node("out", 1, 0)]
    links = [("in", 0, "a", 0), ("a", 0, "b", 0), ("c", 0, "b", 1), ("b", 0, "out", 0)]
    pos = check(boxes, links)
    assert pos["c"][0] == pos["a"][0], "a constant goes in the column before its user"


def test_a_node_fed_by_many_stays_by_its_sources():
    boxes = [node("in", 0, 3), node("m", 3, 1), node("a", 1, 1), node("b", 1, 1), node("out", 2, 0)]
    links = [("in", 0, "m", 0), ("in", 1, "m", 1), ("in", 2, "m", 2), ("in", 0, "a", 0), ("a", 0, "b", 0),
             ("b", 0, "out", 0), ("m", 0, "out", 1)]
    pos = check(boxes, links)
    assert pos["m"][0] == pos["a"][0], "three short links and a long one, not the other way round"


def test_frames_keep_to_themselves():
    boxes = [node("in", 0, 1), node("a", 1, 1, "F"), node("b", 1, 1, "F"), node("c", 1, 1, "G"),
             node("out", 2, 0)]
    frames = [Frame("F", label=10), Frame("G", parent="F")]
    links = [("in", 0, "a", 0), ("a", 0, "b", 0), ("b", 0, "c", 0), ("c", 0, "out", 0), ("in", 0, "out", 1)]
    pos = check(boxes, links, frames)
    r = rects(boxes, pos)

    def bbox(ids):
        return (min(r[i][0] for i in ids), max(r[i][1] for i in ids),
                max(r[i][0] + r[i][2] for i in ids), min(r[i][1] - r[i][3] for i in ids))

    left, top, right, bottom = bbox(["a", "b", "c"])
    for other in ("in", "out"):
        x, y, w, h = r[other]
        outside = x + w <= left or x >= right or y - h >= top or y <= bottom
        assert outside, f"{other} is inside frame F"


def test_cycles_and_unknown_links_do_not_break_it():
    boxes = [node("a", 1, 1, "F"), node("b", 1, 1), node("c", 1, 1, "F")]
    links = [("a", 0, "b", 0), ("b", 0, "c", 0), ("c", 0, "x", 0)]
    check(boxes, links, [Frame("F")])


def test_random_trees_never_overlap():
    rng = random.Random(7)
    for trial in range(60):
        n = rng.randint(2, 30)
        boxes = [node(f"n{i}", rng.randint(0, 5), rng.randint(0, 4), x=rng.uniform(-500, 500),
                      y=rng.uniform(-500, 500)) for i in range(n)]
        frames = [Frame(f"F{k}", parent=(f"F{k - 1}" if k and rng.random() < 0.4 else None),
                        label=rng.choice([0, 12])) for k in range(rng.randint(0, 3))]
        for b in boxes:
            if frames and rng.random() < 0.4:
                b.frame = rng.choice(frames).id
        links = []
        for _ in range(rng.randint(0, 2 * n)):
            a, b = sorted(rng.sample(range(n), 2))
            if boxes[a].outputs and boxes[b].inputs:
                links.append((f"n{a}", rng.randrange(len(boxes[a].outputs)),
                              f"n{b}", rng.randrange(len(boxes[b].inputs))))
        check(boxes, links, frames)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
