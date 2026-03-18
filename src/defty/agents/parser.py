# Copyright (c) 2026 APRL Technologies Inc.
# Author: Yiju Li
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""".defty file parser — convert .defty files into behavior trees.

Uses Python's ast module to parse a restricted subset of Python syntax.
No imports, no function definitions, no arbitrary code execution.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from defty.nodes.base import Node

logger = logging.getLogger(__name__)

__all__ = ["parse_defty_file", "DeftyParseError"]


class DeftyParseError(Exception):
    """Raised when a .defty file cannot be parsed."""


_SAFE_BUILTINS = {"True": True, "False": False, "None": None}


def parse_defty_file(path: str | Path) -> dict[str, Any]:
    """Parse a .defty file and return its metadata and behavior tree."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f".defty file not found: {path}")
    source = path.read_text(encoding="utf-8")
    return parse_defty_source(source, filename=str(path))


def parse_defty_source(source: str, filename: str = "<defty>") -> dict[str, Any]:
    """Parse .defty source code and return the agent definition."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise DeftyParseError(f"Syntax error in {filename}: {exc}") from exc

    _validate_ast(tree, filename)

    from defty.agents.registry import NodeRegistry
    registry = NodeRegistry.default()
    namespace: dict[str, Any] = {}

    for node_name, node_cls in registry.list_nodes().items():
        namespace[node_name] = node_cls

    from defty.agents.ref import AgentRef
    namespace["Agent"] = AgentRef
    namespace.update(_SAFE_BUILTINS)

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                raise DeftyParseError(f"{filename}: only simple variable assignments are allowed")
            var_name = stmt.targets[0].id
            value = _eval_node(stmt.value, namespace, filename)
            namespace[var_name] = value
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            pass  # Allow standalone string literals
        else:
            raise DeftyParseError(f"{filename}:{stmt.lineno}: only assignments and comments are allowed")

    result: dict[str, Any] = {}
    for field in ("name", "version", "robot", "tree"):
        if field not in namespace:
            raise DeftyParseError(f"{filename}: missing required field '{field}'")
        result[field] = namespace[field]

    if not isinstance(result["tree"], Node):
        raise DeftyParseError(f"{filename}: 'tree' must be a Node instance")

    if "dependencies" in namespace:
        result["dependencies"] = namespace["dependencies"]
    return result


def _validate_ast(tree: ast.Module, filename: str) -> None:
    """Walk the AST and reject disallowed constructs."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise DeftyParseError(f"{filename}:{node.lineno}: import statements are not allowed in .defty files")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise DeftyParseError(f"{filename}:{node.lineno}: function definitions are not allowed in .defty files")
        if isinstance(node, ast.ClassDef):
            raise DeftyParseError(f"{filename}:{node.lineno}: class definitions are not allowed in .defty files")
        if isinstance(node, (ast.Delete, ast.Global, ast.Nonlocal)):
            raise DeftyParseError(f"{filename}:{node.lineno}: {type(node).__name__} is not allowed in .defty files")


def _eval_node(node: ast.expr, namespace: dict[str, Any], filename: str) -> Any:
    """Recursively evaluate an AST expression node in a restricted namespace."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in namespace:
            return namespace[node.id]
        raise DeftyParseError(f"{filename}:{node.lineno}: unknown name '{node.id}'")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand, namespace, filename)
    if isinstance(node, ast.List):
        return [_eval_node(elt, namespace, filename) for elt in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(elt, namespace, filename) for elt in node.elts)
    if isinstance(node, ast.Dict):
        keys = [_eval_node(k, namespace, filename) for k in node.keys if k is not None]
        values = [_eval_node(v, namespace, filename) for v in node.values]
        return dict(zip(keys, values))
    if isinstance(node, ast.Call):
        func = _eval_node(node.func, namespace, filename)
        args = [_eval_node(a, namespace, filename) for a in node.args]
        kwargs = {kw.arg: _eval_node(kw.value, namespace, filename) for kw in node.keywords}
        if callable(func):
            try:
                return func(*args, **kwargs)
            except TypeError as exc:
                raise DeftyParseError(f"{filename}:{node.lineno}: error calling {_node_name(node.func)}: {exc}") from exc
        raise DeftyParseError(f"{filename}:{node.lineno}: {_node_name(node.func)} is not callable")
    if isinstance(node, ast.Attribute):
        raise DeftyParseError(f"{filename}:{node.lineno}: attribute access is not allowed in .defty files")
    raise DeftyParseError(f"{filename}:{node.lineno}: unsupported expression type: {type(node).__name__}")


def _node_name(node: ast.expr) -> str:
    """Extract a human-readable name from an AST function-call target."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return repr(node)
