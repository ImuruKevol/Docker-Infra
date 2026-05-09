import datetime
import decimal
import json
import re
import uuid
from urllib.parse import quote


class ImageError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def serialize(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    return value


def row(item):
    return None if item is None else serialize(dict(item))


def parse_json_lines(stdout):
    items = []
    for line in (stdout or "").splitlines():
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgtp]?b)\s*$", re.IGNORECASE)


def parse_size_bytes(value):
    text = str(value or "").strip()
    if not text:
        return 0
    match = SIZE_RE.match(text.replace(" ", ""))
    if not match:
        return 0
    amount = float(match.group(1))
    unit = match.group(2).lower()
    scale = {
        "b": 1,
        "kb": 1024,
        "mb": 1024 ** 2,
        "gb": 1024 ** 3,
        "tb": 1024 ** 4,
        "pb": 1024 ** 5,
    }.get(unit, 1)
    return int(amount * scale)


def encode_repository_name(repository_name):
    raw = str(repository_name or "").strip().strip("/")
    return quote(quote(raw, safe=""), safe="")


def parse_docker_image_lines(stdout):
    items = []
    for payload in parse_json_lines(stdout):
        repository = str(payload.get("Repository") or payload.get("repository") or "").strip()
        tag = str(payload.get("Tag") or payload.get("tag") or "").strip()
        digest = str(payload.get("Digest") or payload.get("digest") or "").strip()
        image_id = str(payload.get("ID") or payload.get("Id") or payload.get("id") or "").strip()
        created_at = str(payload.get("CreatedAt") or "").strip()
        created_since = str(payload.get("CreatedSince") or "").strip()
        size = str(payload.get("Size") or payload.get("VirtualSize") or "").strip()
        if repository in {"", "<none>"} and image_id == "":
            continue
        digest_value = "" if digest == "<none>" else digest
        remove_ref = image_id
        if repository not in {"", "<none>"} and tag not in {"", "<none>"} and digest_value:
            remove_ref = f"{repository}:{tag}@{digest_value}"
        elif repository not in {"", "<none>"} and tag not in {"", "<none>"}:
            remove_ref = f"{repository}:{tag}"
        elif repository not in {"", "<none>"} and digest_value:
            remove_ref = f"{repository}@{digest_value}"
        elif repository not in {"", "<none>"}:
            remove_ref = repository
        items.append(
            {
                "repository": repository,
                "tag": tag,
                "digest": digest_value,
                "image_id": image_id,
                "created_at": created_at,
                "created_since": created_since,
                "size": size,
                "size_bytes": parse_size_bytes(size),
                "containers_count": int(payload.get("Containers") or 0),
                "remove_ref": remove_ref,
                "raw": payload,
            }
        )
    return items


def parse_docker_container_inspect_lines(stdout):
    items = []
    for payload in parse_json_lines(stdout):
        state = payload.get("State") or {}
        timestamps = []
        for value in [state.get("StartedAt"), state.get("FinishedAt"), payload.get("Created")]:
            text = str(value or "").strip()
            if not text or text.startswith("0001-01-01T00:00:00"):
                continue
            timestamps.append(text)
        items.append(
            {
                "container_id": str(payload.get("Id") or "").strip(),
                "name": str(payload.get("Name") or "").strip().lstrip("/"),
                "image_id": str(payload.get("Image") or "").strip(),
                "status": str(state.get("Status") or "").strip(),
                "running": bool(state.get("Running")),
                "created_at": str(payload.get("Created") or "").strip(),
                "last_used_at": max(timestamps) if timestamps else "",
            }
        )
    return items


class ImagesShared:
    ImageError = ImageError
    serialize = staticmethod(serialize)
    row = staticmethod(row)
    parse_docker_image_lines = staticmethod(parse_docker_image_lines)
    parse_docker_container_inspect_lines = staticmethod(parse_docker_container_inspect_lines)
    parse_size_bytes = staticmethod(parse_size_bytes)
    encode_repository_name = staticmethod(encode_repository_name)


Model = ImagesShared()
