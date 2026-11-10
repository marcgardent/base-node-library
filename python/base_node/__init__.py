"""The .bn language: text to a resolved node graph, without bpy."""

from __future__ import annotations

import sys

from .errors import BnError, Diagnostic
from .format import format_source
from .lexer import tokenize
from .parser import parse
from .printer import to_source
from .profiles import check_profile, load_profile
from .typecheck import check


def compile_source(source, schema, filename="<text>", load=None):
    """Parse and check a .bn source. Returns the graphs, raises BnError.

    `load(name, source)` finds the modules of its `use` lines: see typecheck.check.
    """
    return check(parse(source, filename), schema, filename, load)


# Enregistre l'alias interne base_node.lang pointant sur base_node
if __name__ + ".lang" not in sys.modules:
    sys.modules[__name__ + ".lang"] = sys.modules[__name__]

__all__ = [
    "BnError",
    "Diagnostic",
    "parse",
    "check",
    "compile_source",
    "tokenize",
    "to_source",
    "format_source",
    "load_profile",
    "check_profile",
]
