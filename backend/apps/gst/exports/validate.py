"""A deliberately tiny structural validator for the bundled JSON Schemas.

`jsonschema` is not a dependency (CLAUDE.md §4: no new deps), so this checks the subset
we use: type (incl. unions), properties, required, items, enum, additionalProperties and
local "$ref": "#/definitions/..." pointers. Validation in the GSTN offline tool remains a
manual step for the owner."""

import json
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
LOCAL_REF_PREFIX = "#/"

_TYPE_CHECKS: dict[str, Any] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "null": lambda v: v is None,
}


def load_schema(name: str) -> dict[str, Any]:
    with (SCHEMAS_DIR / name).open(encoding="utf-8") as handle:
        schema: dict[str, Any] = json.load(handle)
    return schema


def _type_ok(value: Any, expected: str | list[str]) -> bool:
    names = [expected] if isinstance(expected, str) else expected
    return any(_TYPE_CHECKS[name](value) for name in names)


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith(LOCAL_REF_PREFIX):
        raise ValueError(f"only local $ref pointers are supported, got {ref!r}")
    node: Any = root
    for part in ref[len(LOCAL_REF_PREFIX) :].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"unresolvable $ref {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"$ref {ref!r} does not point at a schema object")
    return node


def validate(
    instance: Any, schema: dict[str, Any], path: str = "$", root: dict[str, Any] | None = None
) -> list[str]:
    """Return a list of human-readable violations (empty when valid)."""
    root = schema if root is None else root
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)
    errors: list[str] = []
    if "type" in schema and not _type_ok(instance, schema["type"]):
        errors.append(f"{path}: expected {schema['type']}, got {type(instance).__name__}")
        return errors
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']}")
    if isinstance(instance, dict):
        properties: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], f"{path}.{key}", root))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected key {key!r}")
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], f"{path}[{index}]", root))
    return errors


def assert_valid(instance: Any, schema_name: str) -> None:
    errors = validate(instance, load_schema(schema_name))
    if errors:
        raise ValueError("; ".join(errors[:10]))
