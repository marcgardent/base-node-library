"""Where Blender drew a socket: read from its runtime data, which Python is not given.

The structures are those of Node Arrange by Leonardo Pike-Excell (GPL-2.0-or-later), cut to
what leads to `bNodeSocketRuntime.location`. They follow Blender's memory layout, which can
change with any release: `drawn_y` checks that what it reads lies on the node, and answers
None otherwise, so that the caller estimates the place instead.
"""

import ctypes
import platform

import bpy

_V = bpy.app.version


class _bNodeStack(ctypes.Structure):
    _fields_ = [
        ("vec", ctypes.c_float * 4), ("min", ctypes.c_float), ("max", ctypes.c_float),
        ("data", ctypes.c_void_p), ("hasinput", ctypes.c_short), ("hasoutput", ctypes.c_short),
        ("datatype", ctypes.c_short), ("sockettype", ctypes.c_short), ("is_copy", ctypes.c_short),
        ("external", ctypes.c_short), ("_pad", ctypes.c_char * 4),
    ]


_runtime = []
if platform.system() == "Windows":
    _runtime.append(("_pad0", ctypes.c_char * 8))
_runtime.append(("declaration", ctypes.c_void_p))
if _V >= (5, 2, 0):
    _runtime.append(("identifier_ustr", ctypes.c_char * 8))
_runtime += [("changed_flag", ctypes.c_uint32), ("total_inputs", ctypes.c_short)]
if _V >= (5, 0, 0):
    _runtime.append(("inferred_structure_type", ctypes.c_int8))
_runtime += [("_pad1", ctypes.c_byte * 1), ("location", ctypes.c_float * 2)]


class _bNodeSocketRuntime(ctypes.Structure):
    _fields_ = _runtime


_socket = [
    ("next", ctypes.c_void_p), ("prev", ctypes.c_void_p), ("prop", ctypes.c_void_p),
    ("identifier", ctypes.c_char * 64), ("name", ctypes.c_char * 64), ("storage", ctypes.c_void_p),
    ("type", ctypes.c_short), ("flag", ctypes.c_short), ("limit", ctypes.c_short), ("in_out", ctypes.c_short),
    ("typeinfo", ctypes.c_void_p), ("idname", ctypes.c_char * 64), ("default_value", ctypes.c_void_p),
    ("stack_index", ctypes.c_int if _V >= (5, 0, 0) else ctypes.c_short),
    ("display_shape", ctypes.c_char), ("attribute_domain", ctypes.c_char),
    ("_pad", ctypes.c_char * (2 if _V >= (5, 0, 0) else 4)),
    ("label", ctypes.c_char * 64), ("description", ctypes.c_char * 64),
]
if _V < (5, 1, 0):
    _socket.append(("short_label", ctypes.c_char * 64))
_socket += [
    ("default_attribute_name", ctypes.POINTER(ctypes.c_char)), ("own_index", ctypes.c_int),
    ("to_index", ctypes.c_int), ("link", ctypes.c_void_p), ("ns", _bNodeStack),
    ("runtime", ctypes.POINTER(_bNodeSocketRuntime)),
]


class _bNodeSocket(ctypes.Structure):
    _fields_ = _socket


def drawn_y(socket, scale, left, top, width, height):
    """The y where `socket` was last drawn, when it lies on its node's box; None otherwise."""
    try:
        x, y = _bNodeSocket.from_address(socket.as_pointer()).runtime.contents.location
    except (ValueError, OSError):
        return None
    x, y = x / scale, y / scale
    if left - 12 <= x <= left + width + 12 and top - height + 1 < y < top - 1:
        return y
    return None
