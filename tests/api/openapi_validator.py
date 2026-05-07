class OpenApiValidationError(AssertionError):
    pass


_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool,
}


def resolve_ref(document, ref):
    if not ref.startswith("#/"):
        raise OpenApiValidationError(f"unsupported ref: {ref}")

    current = document
    for part in ref[2:].split("/"):
        current = current[part]
    return current


def assert_schema(document, schema, value, path="$"):
    if value is None:
        if schema.get("nullable") is True:
            return
        raise OpenApiValidationError(f"{path}: value is null but schema is not nullable")

    if "$ref" in schema:
        return assert_schema(document, resolve_ref(document, schema["$ref"]), value, path)

    expected_type = schema.get("type")
    if expected_type:
        expected = _TYPE_MAP[expected_type]
        if expected_type == "integer":
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected)
        if not valid:
            raise OpenApiValidationError(f"{path}: expected {expected_type}, got {type(value).__name__}")

    if "enum" in schema and value not in schema["enum"]:
        raise OpenApiValidationError(f"{path}: {value!r} is not in enum {schema['enum']!r}")

    if expected_type == "object":
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise OpenApiValidationError(f"{path}: missing required property {key}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise OpenApiValidationError(f"{path}: unexpected properties {extras!r}")

        for key, child_schema in properties.items():
            if key in value:
                assert_schema(document, child_schema, value[key], f"{path}.{key}")

    if expected_type == "array":
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            assert_schema(document, item_schema, item, f"{path}[{index}]")
