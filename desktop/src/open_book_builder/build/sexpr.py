"""Minimal S-expression reader for KiCad files.

Nodes are Python lists. Atoms are `Sym` (bare words), `str` (quoted) or numbers.
"""
from __future__ import annotations

import re
import sys


class Sym(str):
    """A bare (unquoted) atom."""


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')
_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


def parse(text: str):
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    stack: list[list] = [[]]
    pos = 0
    end = len(text)
    while pos < end:
        m = _TOKEN.match(text, pos)
        if not m:
            break
        pos = m.end()
        open_, close, quoted, atom = m.groups()
        if open_:
            stack.append([])
        elif close:
            node = stack.pop()
            stack[-1].append(node)
        elif quoted is not None:
            stack[-1].append(re.sub(r"\\(.)", r"\1", quoted))
        elif atom is not None:
            if _NUMBER.match(atom):
                stack[-1].append(int(atom) if re.fullmatch(r"[+-]?\d+", atom) else float(atom))
            else:
                stack[-1].append(Sym(atom))
    return stack[0][0] if stack[0] else None


def head(node) -> str | None:
    if isinstance(node, list) and node and isinstance(node[0], Sym):
        return str(node[0])
    return None


def positional(node) -> list:
    return node[1:] if isinstance(node, list) else []


def find_tagged(node, tag: str):
    for child in node if isinstance(node, list) else []:
        if head(child) == tag:
            return child
    return None


def find_all_tagged(node, tag: str) -> list:
    return [c for c in (node if isinstance(node, list) else []) if head(c) == tag]
