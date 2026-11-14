---
name: add-tnr
argument-hint: <github-url> [version]
description: Add a third-party Geometry Nodes library, given by a GitHub URL, to Base Node's non-regression tests (TNR) - check its license, find its .blend, pin it by version and sha256, write tests/libraries/<name>.toml, run the round-trip and write its baseline, sort what it finds into Base Node bugs, then open a PR with the CI. Use when Marc gives a GitHub repo of node groups (an add-on, an asset library) and asks to "test it", "add it as TNR / regression corpus", "intégrer une lib GN en TNR", or to bump such a library to a new version.
---

# A Geometry Nodes library from GitHub as non-regression test

`/add-tnr <github-url> [version]`: the URL is the library's repository; without a version, take its latest
release (or, with no release, the default branch's last commit) and say which.

The goal: every Geometry Nodes group of a real library goes `tree -> .bn -> tree -> .bn` and is evaluated
beside its original, at a fixed version, in CI, so that a change of the reader, the builder or the language
that changes what happens to any group fails the test until its baseline is written again on purpose.

The machinery exists: `base-node-for-blender/tests/test_libraries.py`, the manifests and baselines in
`base-node-for-blender/tests/libraries/` (read its README first), and the `blender` job of
`.github/workflows/ci.yml`. Adding a library is a manifest, a baseline and a line of credits. Molecular Nodes
(`molecularnodes.toml`) is the worked example.

Work in the scratchpad for everything downloaded: clone with `--depth 1` into its own empty directory and never
run the library's code (no `uv run`, no add-on install). A `.blend` can hold scripts: open it only with
`--factory-startup` in background mode, where they do not run.

## 1. License

Read the repo's `LICENSE` (and `pyproject.toml`, `blender_manifest.toml`, the README: they may disagree; the
`LICENSE` file wins, and a `LICENSE.OLD` or upstream notice must be kept if anything is copied).

Base Node's tests live in `base-node-for-blender/`, which is GPL-3.0-or-later (see the root README, *License*).

| Library license | Fetch at test time | Commit the `.blend` / `.bn` | Credit |
|---|---|---|---|
| CC0, Unlicense | yes | yes | thank them anyway |
| MIT, BSD, Apache-2.0, zlib | yes | yes, keep their notice beside the file | required |
| GPL-2.0-or-later, GPL-3.0(-or-later), LGPL | yes | yes (compatible) | required |
| CC-BY(-SA) | yes | yes, with attribution | required |
| GPL-2.0-only, CC-BY-NC, CC-BY-ND, proprietary, **no license at all** | yes, for our own test only | **no** | name them |

Fetching is the default even when committing is allowed: nothing large in the repository, and a new version
is one line of the manifest. The baseline holds only group names, statuses and hashes, never their text.
Commit a library (`file = "…"` in the manifest, the way `tests/fixtures/everyday_geometry_nodes.blend` is)
only when Marc wants its `.bn` texts readable in the repo; then add it to the root README's *License* list.
When the license is unclear, say so and ask Marc before going on.

## 2. Find the node groups

The `.blend` that holds them is rarely the obvious one. In order:

1. `git ls-files '*.blend'` in the clone: an asset library usually commits it.
2. If node groups are built from code (Molecular Nodes: `molecularnodes/nodes/**/*.py` -> `assets/nodes.blend`,
   gitignored; look for `.gitignore`d `*.blend`, `AGENTS.md`, `CONTRIBUTING.md`, a `build` command), take the
   built file from a **release asset**: `gh release list -R owner/repo`, then
   `gh release view <tag> -R owner/repo --json assets` and `unzip -l` a downloaded zip to find the member.
   Prefer a release to a build: it is what users have, and it needs no tool of theirs.
3. Git LFS (`.gitattributes`): use the `media.githubusercontent.com` URL of the file at a commit.

Pin it:
- a committed file: `url = "https://raw.githubusercontent.com/<owner>/<repo>/<commit>/<path>"` at a full commit
  hash (`git rev-parse HEAD`), `version` = the short hash or the tag;
- a release: `url` of the asset at its tag, `member` = the path inside the zip (read by HTTP ranges, only that
  member is downloaded; check `curl -sIL -r 0-0 <url>` answers `206`), `version` = the tag.

`sha256` is the hash of the `.blend` itself (`sha256sum`), not of the zip. Note its `blender_version_min`: the
test must run with a Blender at least that recent (CI uses the version in `.github/workflows/ci.yml`).

## 3. Manifest and first run

Write `base-node-for-blender/tests/libraries/<name>.toml` like `molecularnodes.toml`: `name`, `author`,
`homepage`, `license`, a comment on why it is fetched or committed, `version`, `url` (+ `member`) or `file`,
`sha256`. `<name>` is short, lowercase, no spaces: it is the baseline's name and the test's argument.

```bash
blender --background --factory-startup --python-exit-code 1 \
  --python base-node-for-blender/tests/test_libraries.py -- <name>
```

Run it from a clean checkout of the commit the baseline is for (`git worktree add <scratchpad>/wt -b
tnr/<name> main`, then work there): other sessions may be editing the reader or the builder in the main
checkout, and a baseline written against half-written code is worthless. `git status` first.

With no baseline yet, the run writes it. Run it a **second** time: it must pass unchanged, or something is not
deterministic (a simulation, a random node without seed, a frame-dependent group): find which groups change
between runs and say so before going on; never keep a baseline that a rerun does not reproduce. A few hundred
groups take about five minutes.

## 4. Sort what it finds

The baseline's `summary` says how many groups are `ok`; every other status is either a Base Node bug or a
limit of the test. Group them by cause, not by group: the first `error` lines, and for `unstable` groups a
`diff` of the two texts (`texts/<name>/` in the cache holds the first read; build it and read again to see the
second). For `evaluates_otherwise`, first check the original is deterministic (evaluate it twice) before
blaming Base Node.

- A bug of the test itself (the fingerprint, the caller tree): fix it in `tests/test_extension.py`, rerun.
- A Base Node bug: do **not** fix it in the same change. List it for Marc, one line per cause with the number of
  groups and one example group, and propose each fix as its own follow-up; the baseline records the bug today
  and its fix will show as `↑ group: build_error -> ok` lines.
- Warnings (`appearance … not exported`, `… replaced`): what the text loses; list the kinds, not every group.

## 5. Credits, CI, PR

- Add the library to the table of `tests/libraries/README.md` (version, author, license).
- The `blender` job of `.github/workflows/ci.yml` runs every manifest and caches `~/.cache/base-node`; a new
  library needs nothing there unless it needs a newer Blender than the job installs.
- Run the whole Blender suite (`tests/test_extension.py`) too if the test helpers changed.
- Branch, commit (manifest, baseline, README, any test fix), and ask Marc before pushing or opening the PR. The
  PR text says: the library, version and license, why fetched or committed, the summary line, and the bugs found.

## Bumping a library

Change `version`, `url`, `sha256` in its manifest, rerun with `BASE_NODE_UPDATE_FIXTURES=1`, and read the
baseline's diff: new and gone groups, and status changes, are the library's changes, not Base Node's; say which
is which in the PR.
