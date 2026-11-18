"""
Function-only problem signatures and starter-code generation.

A problem opts into function-only judging by storing ``function_signature``:

    {
      "name": "twoSum",
      "params": [
        {"name": "nums", "type": "int[]"},
        {"name": "target", "type": "int"}
      ],
      "return_type": "int[]"
    }

Supported types are ``int``, ``long``, ``double``, ``bool`` and ``string``,
optionally wrapped in one or two ``[]`` dimensions. Nested arrays are limited to
``int[][]`` and ``string[][]`` so every language has a simple, predictable
representation.

The judge (judge/codegen.py) mirrors this schema. Keep the two type tables in
sync when adding a type.
"""

from __future__ import annotations

import json
import re
from typing import Any

LANGUAGES = ("python", "cpp", "java", "javascript")
BASE_TYPES = ("int", "long", "double", "bool", "string")
MAX_DIMENSIONS = 2
NESTED_BASES = ("int", "string")

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SignatureError(ValueError):
    """The function signature is missing a required fact or has an unknown type."""


def parse_type(type_name: Any) -> tuple[str, int]:
    """Split ``"int[][]"`` into ``("int", 2)``, rejecting anything unsupported."""
    if not isinstance(type_name, str) or not type_name:
        raise SignatureError("Each parameter and the return type need a type.")
    base = type_name
    dimensions = 0
    while base.endswith("[]"):
        base = base[:-2]
        dimensions += 1
    if base not in BASE_TYPES:
        raise SignatureError(
            f"Unknown type {type_name!r}. Supported base types: {', '.join(BASE_TYPES)}."
        )
    if dimensions > MAX_DIMENSIONS:
        raise SignatureError(f"Type {type_name!r} has too many dimensions (max {MAX_DIMENSIONS}).")
    if dimensions == MAX_DIMENSIONS and base not in NESTED_BASES:
        raise SignatureError(
            f"Nested arrays are supported for {', '.join(NESTED_BASES)} only (got {type_name!r})."
        )
    return base, dimensions


def normalize_type(type_name: str) -> str:
    base, dimensions = parse_type(type_name)
    return base + "[]" * dimensions


def validate_signature(raw: Any) -> dict:
    """Return a normalized copy of *raw* or raise :class:`SignatureError`."""
    if not isinstance(raw, dict):
        raise SignatureError("The function signature must be a JSON object.")

    name = raw.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SignatureError("The function name must be a valid identifier (letters, digits, _).")

    params = raw.get("params")
    if not isinstance(params, list):
        raise SignatureError("The function signature needs a 'params' list.")
    if len(params) > 10:
        raise SignatureError("At most 10 parameters are supported.")

    seen: set[str] = set()
    normalized_params = []
    for index, param in enumerate(params):
        if not isinstance(param, dict):
            raise SignatureError(f"Parameter {index + 1} must be an object with 'name' and 'type'.")
        param_name = param.get("name")
        if not isinstance(param_name, str) or not _NAME_RE.match(param_name):
            raise SignatureError(f"Parameter {index + 1} needs a valid identifier name.")
        if param_name in seen:
            raise SignatureError(f"Duplicate parameter name {param_name!r}.")
        seen.add(param_name)
        normalized_params.append({
            "name": param_name,
            "type": normalize_type(param.get("type")),
        })

    return {
        "name": name,
        "params": normalized_params,
        "return_type": normalize_type(raw.get("return_type")),
    }


# ─── Type rendering ───────────────────────────────────────────────────────────

def _python_type(base: str, dimensions: int) -> str:
    scalar = {"int": "int", "long": "int", "double": "float", "bool": "bool", "string": "str"}[base]
    for _ in range(dimensions):
        scalar = f"List[{scalar}]"
    return scalar


def _cpp_type(base: str, dimensions: int) -> str:
    scalar = {"int": "int", "long": "long long", "double": "double", "bool": "bool", "string": "string"}[base]
    for _ in range(dimensions):
        scalar = f"vector<{scalar}>"
    return scalar


def _java_type(base: str, dimensions: int) -> str:
    scalar = {"int": "int", "long": "long", "double": "double", "bool": "boolean", "string": "String"}[base]
    return scalar + "[]" * dimensions


def _jsdoc_type(base: str, dimensions: int) -> str:
    scalar = {"int": "number", "long": "number", "double": "number", "bool": "boolean", "string": "string"}[base]
    return scalar + "[]" * dimensions


def _cpp_param_type(base: str, dimensions: int) -> str:
    rendered = _cpp_type(base, dimensions)
    # LeetCode convention: arrays by reference, strings by value, scalars by value.
    return f"{rendered}&" if dimensions else rendered


def _cpp_default(base: str, dimensions: int) -> str:
    if dimensions:
        return "{}"
    return {
        "int": "0",
        "long": "0",
        "double": "0.0",
        "bool": "false",
        "string": '""',
    }[base]


def _java_default(base: str, dimensions: int) -> str:
    if dimensions:
        return f"new {_java_type(base, dimensions - 1)}[]{{}}"
    return {
        "int": "0",
        "long": "0L",
        "double": "0.0",
        "bool": "false",
        "string": '""',
    }[base]


# ─── Starter code ─────────────────────────────────────────────────────────────

def starter_code(signature: Any, language: str) -> str:
    """A minimal editor template: the function/class only, no stdin or stdout."""
    if language not in LANGUAGES:
        raise SignatureError(f"Unsupported language {language!r}.")
    sig = validate_signature(signature)
    name = sig["name"]
    params = sig["params"]
    return_base, return_dims = parse_type(sig["return_type"])

    if language == "python":
        args = ", ".join(
            f"{param['name']}: {_python_type(*parse_type(param['type']))}" for param in params
        )
        signature_line = f"    def {name}(self{', ' if args else ''}{args}) -> {_python_type(return_base, return_dims)}:"
        return (
            "from typing import List\n\n\n"
            "class Solution:\n"
            f"{signature_line}\n"
            "        # Your solution here\n"
            "        pass\n"
        )

    if language == "cpp":
        args = ", ".join(
            f"{_cpp_param_type(*parse_type(param['type']))} {param['name']}" for param in params
        )
        return (
            "#include <bits/stdc++.h>\n"
            "using namespace std;\n\n"
            "class Solution {\n"
            "public:\n"
            f"    {_cpp_type(return_base, return_dims)} {name}({args}) {{\n"
            "        // Your solution here\n"
            f"        return {_cpp_default(return_base, return_dims)};\n"
            "    }\n"
            "};\n"
        )

    if language == "java":
        args = ", ".join(
            f"{_java_type(*parse_type(param['type']))} {param['name']}" for param in params
        )
        return (
            "import java.util.*;\n\n"
            "class Solution {\n"
            f"    public {_java_type(return_base, return_dims)} {name}({args}) {{\n"
            "        // Your solution here\n"
            f"        return {_java_default(return_base, return_dims)};\n"
            "    }\n"
            "}\n"
        )

    args = ", ".join(param["name"] for param in params)
    jsdoc_args = "\n".join(
        f" * @param {{{_jsdoc_type(*parse_type(param['type']))}}} {param['name']}" for param in params
    )
    jsdoc = (
        "/**\n"
        f"{jsdoc_args + chr(10) if jsdoc_args else ''}"
        f" * @return {{{_jsdoc_type(return_base, return_dims)}}}\n"
        " */\n"
    )
    return (
        f"{jsdoc}"
        f"var {name} = function({args}) {{\n"
        "    // Your solution here\n"
        "};\n"
    )


def all_starters(signature: Any) -> dict[str, str]:
    """``{"starter_code_python": ..., ...}`` for ``Problem``."""
    return {f"starter_code_{language}": starter_code(signature, language) for language in LANGUAGES}


# ─── Test-case validation (admin edits) ───────────────────────────────────────
# Mirrors the judge's encoder (judge/codegen.py), so a test case that saves
# here can always be fed to the generated harnesses.

_INT_RANGES = {"int": (-(2**31), 2**31 - 1), "long": (-(2**63), 2**63 - 1)}


def _check_value(type_name: str, value: Any, where: str, *, input_value=False) -> None:
    base, dimensions = parse_type(type_name)
    if dimensions:
        if not isinstance(value, list):
            raise ValueError(f"{where}: expected an array ({type_name}).")
        inner = base + "[]" * (dimensions - 1)
        for index, item in enumerate(value):
            _check_value(inner, item, f"{where}[{index}]", input_value=input_value)
        return
    if base == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{where}: expected true or false.")
    elif base in _INT_RANGES:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{where}: expected an integer.")
        low, high = _INT_RANGES[base]
        if not low <= value <= high:
            raise ValueError(f"{where}: {value} does not fit in a {base}.")
    elif base == "double":
        import math
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{where}: expected a number.")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"{where}: expected a finite number.")
    else:
        if not isinstance(value, str):
            raise ValueError(f"{where}: expected a string.")
        if input_value and ("\n" in value or "\r" in value):
            raise ValueError(f"{where}: strings may not contain line breaks.")


def validate_input(signature: Any, input_data: str) -> None:
    """Raise ValueError unless `input_data` is a JSON object with exactly the
    signature's parameters, each of the declared type."""
    sig = validate_signature(signature)
    try:
        payload = json.loads(input_data)
    except (TypeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        raise ValueError('Input must be a JSON object keyed by parameter name, e.g. {"nums": [1, 2], "target": 3}.')
    names = [param["name"] for param in sig["params"]]
    missing = [name for name in names if name not in payload]
    if missing:
        raise ValueError(f"Missing parameter(s): {', '.join(missing)}.")
    unknown = sorted(set(payload) - set(names))
    if unknown:
        raise ValueError(f"Unknown parameter(s): {', '.join(unknown)}.")
    for param in sig["params"]:
        _check_value(param["type"], payload[param["name"]], param["name"], input_value=True)


def validate_expected(signature: Any, expected_output: str, compare_mode: str = "EXACT") -> None:
    """Raise ValueError unless `expected_output` is the JSON form of a value of
    the return type (what the harness prints); UNORDERED needs an array."""
    sig = validate_signature(signature)
    try:
        value = json.loads(expected_output)
    except (TypeError, ValueError):
        raise ValueError('Expected output must be the returned value as JSON, e.g. [0, 1], 42, true or "abc".') from None
    if (compare_mode or "").upper() == "UNORDERED" and not isinstance(value, list):
        raise ValueError("Unordered comparison needs a JSON array as the expected output.")
    _check_value(sig["return_type"], value, "Expected output")


# ─── Sample display ───────────────────────────────────────────────────────────

def format_input(signature: Any, input_data: str) -> str:
    """Render a JSON test-case input as ``nums = [2, 7], target = 9``.

    Anything that does not match the signature is returned unchanged, so legacy
    stdin/stdout test cases keep their original presentation.
    """
    try:
        sig = validate_signature(signature)
    except SignatureError:
        return input_data
    try:
        values = json.loads(input_data)
    except (TypeError, ValueError):
        return input_data
    if not isinstance(values, dict):
        return input_data
    parts = []
    for param in sig["params"]:
        if param["name"] not in values:
            return input_data
        rendered = json.dumps(values[param["name"]], ensure_ascii=False)
        parts.append(f"{param['name']} = {rendered}")
    return ", ".join(parts)
