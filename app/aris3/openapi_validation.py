from __future__ import annotations

from collections.abc import Mapping, Sequence


def _resolve_local_ref(spec: dict, ref: str):
    if not ref.startswith("#/"):
        raise ValueError(f"Only local refs are supported: {ref}")

    node = spec
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, Mapping) or token not in node:
            raise KeyError(ref)
        node = node[token]
    return node


def find_unresolved_openapi_refs(spec: dict) -> list[str]:
    errors: list[str] = []

    def _walk(node, pointer: str) -> None:
        if isinstance(node, Mapping):
            ref = node.get("$ref")
            if isinstance(ref, str):
                try:
                    _resolve_local_ref(spec, ref)
                except Exception:
                    errors.append(f"{pointer}: unresolved $ref -> {ref}")
            for key, value in node.items():
                child = f"{pointer}/{key}" if pointer else f"/{key}"
                _walk(value, child)
            return

        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for index, item in enumerate(node):
                child = f"{pointer}/{index}" if pointer else f"/{index}"
                _walk(item, child)

    _walk(spec, "")
    return errors


def assert_semantically_valid_openapi(spec: dict) -> None:
    errors = find_unresolved_openapi_refs(spec)
    if errors:
        joined = "\n".join(errors[:20])
        raise AssertionError(f"OpenAPI semantic validation failed with unresolved refs:\n{joined}")
