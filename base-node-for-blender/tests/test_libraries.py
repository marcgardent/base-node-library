"""Non-regression tests on third-party Geometry Nodes libraries.

Each `tests/libraries/<name>.toml` names a .blend: in the repository (`file`), or fetched at a fixed
version (`url`, and `member` when it lies in a .zip), checked by its `sha256`. Every Geometry Nodes group
of it is read as .bn text, built back from that text, read again and evaluated beside the original.
What happens to each group is kept in `tests/libraries/<name>.baseline.json`: its status, the first
error, the warnings and a hash of its text. The test fails when that changes, for better or worse.

Run in Blender via:
    blender --background --factory-startup --python-exit-code 1 \
      --python base-node-for-blender/tests/test_libraries.py [-- <name> ...]

When the change is wanted (a fix, a reader that writes otherwise), write the baselines again and review
their diff: BASE_NODE_UPDATE_FIXTURES=1. The texts of the last run are kept in the cache
($BASE_NODE_CACHE, ~/.cache/base-node by default) under texts/<name>, those of the run before under
texts/<name>.previous: `diff -r` them to read what changed.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sys
import tomllib
import traceback
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_extension as T  # noqa: E402  (loads base_node)

import bpy  # noqa: E402

LIBRARIES = T.EXT_DIR / "tests" / "libraries"
CACHE = Path(os.environ.get("BASE_NODE_CACHE") or Path.home() / ".cache" / "base-node")
KINDS = ("mesh", "curves", "mesh caller", "mesh caller fed")


class RangeFile(io.RawIOBase):
    """A remote file read by HTTP ranges: zipfile reads only the directory and the member it needs."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as r:
            self.url, self.size = r.url, int(r.headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = (offset, self.pos + offset, self.size + offset)[whence]
        return self.pos

    def read(self, n=-1):
        end = self.size if n is None or n < 0 else min(self.size, self.pos + n)
        if end <= self.pos:
            return b""
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end - 1}"})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def fetch(lib):
    """The path of the library's .blend, fetched once into the cache and checked by its hash."""
    if "file" in lib:
        path = LIBRARIES / lib["file"]
    else:
        path = CACHE / "libraries" / f"{lib['sha256']}.blend"
        if not path.exists():
            print(f"   fetching {lib['url']}" + (f" :: {lib['member']}" if "member" in lib else ""))
            if "member" in lib:
                with zipfile.ZipFile(RangeFile(lib["url"])) as z:
                    data = z.read(lib["member"])
            else:
                with urllib.request.urlopen(lib["url"]) as r:
                    data = r.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.with_suffix(".part").write_bytes(data)
            path.with_suffix(".part").rename(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == lib["sha256"], f"{path}: sha256 {digest}, expected {lib['sha256']}"
    return path


def first_error(e):
    """The first line of an error, without its file:line:col, which move with the text."""
    line = (str(e).strip().splitlines() or [type(e).__name__])[0]
    return re.sub(r"^\S+\.bn:\d+:\d+\s+", "", line)


def warning_kind(w):
    """A warning without the group it is about nor its counts: what kind of loss it is."""
    return re.sub(r"\s*\(\d+\)$", "", w.split(": ", 1)[-1])


def round_trip(blend):
    """{group: record} and {group: text} for every Geometry Nodes group of `blend`."""
    from base_node.host import build_source, export_tree
    from base_node.lang.schema import key

    for g in list(bpy.data.node_groups):
        bpy.data.node_groups.remove(g)
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.node_groups = list(src.node_groups)
    loaded = list(dst.node_groups)
    groups = sorted((g for g in loaded if g.bl_idname == "GeometryNodeTree"), key=lambda g: g.name)

    records, texts = {}, {}
    for g in groups:
        r = records[g.name] = {"status": "ok"}
        try:
            text, warnings = export_tree(g)
        except Exception as e:
            r.update(status="export_error", error=first_error(e))
            continue
        texts[g.name] = text
        r["text"] = hashlib.sha256(text.encode()).hexdigest()[:16]
        kinds = sorted({warning_kind(w) for w in warnings})
        if kinds:
            r["warnings"] = kinds

    originals = {}
    for g in loaded:
        name = g.name
        g.name = f"original {name}"
        originals[name] = g

    for name, text in texts.items():
        r = records[name]
        try:
            tree = build_source(text, filename=f"{key(name)}.bn")[-1]
            assert tree.name == name, f"builds a group named {tree.name!r}"
            again, _ = export_tree(tree)
        except Exception as e:
            r.update(status="build_error", error=first_error(e))
            continue
        if again != text:
            r["status"] = "unstable"
            continue
        differs = []
        for kind in KINDS:
            try:
                if T.evaluate(originals[name], kind) != T.evaluate(bpy.data.node_groups[name], kind):
                    differs.append(kind)
            except Exception as e:
                differs.append(f"{kind}: {first_error(e)}")
        if differs:
            r.update(status="evaluates_otherwise", on=differs)
    for o in [o for o in bpy.data.objects if o.users_scene]:
        bpy.data.objects.remove(o)
    return records, texts


def keep_texts(name, texts):
    """The texts of this run in the cache, those of the run before beside them."""
    from base_node.lang.schema import key

    here = CACHE / "texts" / name
    previous = here.with_name(f"{name}.previous")
    if here.exists():
        shutil.rmtree(previous, ignore_errors=True)
        here.rename(previous)
    here.mkdir(parents=True)
    for group, text in texts.items():
        (here / f"{key(group)}.bn").write_text(text, encoding="utf-8")
    return here


def compare(want, got):
    """Lines saying what changed from the baseline `want` to the run `got`."""
    lines = []
    for name in sorted(want.keys() | got.keys()):
        a, b = want.get(name), got.get(name)
        if a == b:
            continue
        if a is None:
            lines.append(f"+ {name}: new group, {b['status']}")
        elif b is None:
            lines.append(f"- {name}: group gone")
        elif a["status"] != b["status"]:
            better = b["status"] == "ok"
            lines.append(f"{'↑' if better else '↓'} {name}: {a['status']} -> {b['status']}"
                         + (f" ({b.get('error') or b.get('on')})" if not better else ""))
        else:
            what = [k for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)]
            lines.append(f"~ {name}: {', '.join(what)} changed"
                         + (f": {b.get('error')}" if "error" in what else ""))
    return lines


def summary(records):
    counts = {}
    for r in records.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return ", ".join(f"{n} {s}" for s, n in sorted(counts.items(), key=lambda x: -x[1]))


def test_library(manifest):
    lib = tomllib.loads(manifest.read_text(encoding="utf-8"))
    name = manifest.stem
    print(f"-> {lib['name']} {lib.get('version', '')} ({lib['license']})")
    records, texts = round_trip(fetch(lib))
    kept = keep_texts(name, texts)
    print(f"   {len(records)} groups: {summary(records)}; texts in {kept}")
    baseline_path = manifest.with_suffix(".baseline.json")
    if os.environ.get("BASE_NODE_UPDATE_FIXTURES") or not baseline_path.exists():
        baseline = {"library": lib["name"], "version": lib.get("version"), "sha256": lib["sha256"],
                    "blender": bpy.app.version_string, "summary": summary(records), "groups": records}
        baseline_path.write_text(json.dumps(baseline, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"   baseline written: {baseline_path.name}")
        return
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("blender") != bpy.app.version_string:
        print(f"   note: baseline made with Blender {baseline.get('blender')}, this is {bpy.app.version_string}")
    changes = compare(baseline["groups"], records)
    assert not changes, (f"{lib['name']} reads otherwise than {baseline_path.name} "
                         f"({len(changes)} groups); if that is wanted, rerun with BASE_NODE_UPDATE_FIXTURES=1\n"
                         + "\n".join(changes[:80]))
    print(f"   ✓ as in {baseline_path.name}")


def main():
    names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    manifests = sorted(LIBRARIES.glob("*.toml"))
    if names:
        manifests = [m for m in manifests if m.stem in names]
        assert manifests, f"no library named {names} in {LIBRARIES}"
    print("=== Base Node non-regression on third-party libraries ===")
    T.base_node.register()
    failed = 0
    for m in manifests:
        try:
            test_library(m)
        except Exception:
            failed += 1
            traceback.print_exc()
    if failed:
        print(f"\n❌ FAILED: {failed}/{len(manifests)} libraries changed")
        sys.exit(1)
    print(f"\n✅ SUCCESS: {len(manifests)} libraries as in their baselines")
    sys.exit(0)


if __name__ == "__main__":
    main()
