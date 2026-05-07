import mimetypes
import os
from pathlib import Path


config = wiz.config("docker_infra")
settings = wiz.model("struct/settings")

GENERAL_KEYS = {"browser_title": "general.browser_title"}

FIXED_ASSET_ROUTES = {
    "favicon": "/api/system/assets/favicon",
    "logo": "/api/system/assets/logo",
}

DEFAULT_APPEARANCE = {
    "browser_title": "Docker Infra",
    "favicon_url": FIXED_ASSET_ROUTES["favicon"],
    "logo_url": "",
}

ASSET_ROUTE_PREFIX = "/api/system/assets/"
ALLOWED_EXTENSIONS = {
    "favicon": {".ico", ".png", ".svg", ".gif", ".jpg", ".jpeg", ".webp"},
    "logo": {".png", ".svg", ".gif", ".jpg", ".jpeg", ".webp"},
}
CONTENT_TYPE_TO_EXTENSION = {
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
DEFAULT_ASSET_PATHS = {
    "favicon": ("src", "assets", "brand", "icon.ico"),
    "logo": ("src", "assets", "brand", "logo-black.svg"),
}


def _settings_map(env=None):
    return {item["key"]: item for item in settings.list(env=env)}


def _setting_value(mapped, key, default_value):
    row = mapped.get(key)
    if row is None:
        return default_value
    value = row.get("value")
    if value is None:
        return default_value
    return value


def _asset_dir(env=None):
    path = Path(config.system_assets_dir(env))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _guess_extension(kind, filename, content_type):
    suffix = Path(filename or "").suffix.lower()
    if suffix in ALLOWED_EXTENSIONS[kind]:
        return suffix
    if content_type in CONTENT_TYPE_TO_EXTENSION:
        guessed = CONTENT_TYPE_TO_EXTENSION[content_type]
        if guessed in ALLOWED_EXTENSIONS[kind]:
            return guessed
    guessed = mimetypes.guess_extension(content_type or "") or ""
    if guessed in ALLOWED_EXTENSIONS[kind]:
        return guessed
    return ".png" if kind == "logo" else ".ico"


def _fixed_asset_path(kind, env=None):
    base_dir = _asset_dir(env).resolve()
    prefix = f"{kind}."
    for candidate in sorted(base_dir.iterdir()) if base_dir.exists() else []:
        if candidate.is_file() and candidate.name.startswith(prefix):
            return candidate.resolve()
    return None


def _default_asset_path(kind):
    try:
        parts = DEFAULT_ASSET_PATHS[kind]
        return Path(wiz.project.fs(*parts[:-1]).abspath(parts[-1])).resolve()
    except Exception:
        return None


def _asset_public_url(kind, env=None):
    if kind == "favicon":
        return FIXED_ASSET_ROUTES["favicon"]
    return FIXED_ASSET_ROUTES["logo"] if _fixed_asset_path("logo", env=env) is not None else ""


class Appearance:
    def public_payload(self, env=None):
        mapped = _settings_map(env=env)
        return {
            "browser_title": _setting_value(mapped, GENERAL_KEYS["browser_title"], DEFAULT_APPEARANCE["browser_title"]),
            "favicon_url": _asset_public_url("favicon", env=env),
            "logo_url": _asset_public_url("logo", env=env),
        }

    def save(self, payload, test_run_id=None, env=None):
        payload = dict(payload or {})
        saved = {}
        for field, key in GENERAL_KEYS.items():
            saved[field] = str(payload.get(field, "") or "").strip()
            settings.upsert(
                key=key,
                value=saved[field],
                value_type="string",
                description=f"General setting: {field}",
                test_run_id=test_run_id,
                metadata={"group": "general", "kind": field},
                env=env,
            )
        return self.public_payload(env=env)

    def store_asset(self, kind, file_storage, env=None):
        if kind not in ALLOWED_EXTENSIONS:
            raise ValueError("지원하지 않는 asset 종류입니다.")
        if file_storage is None:
            raise ValueError("업로드 파일이 없습니다.")

        filename = getattr(file_storage, "filename", "") or ""
        content_type = getattr(file_storage, "mimetype", None) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        extension = _guess_extension(kind, filename, content_type)
        target_name = f"{kind}{extension}"
        target_path = _asset_dir(env) / target_name
        for candidate in list(_asset_dir(env).glob(f"{kind}.*")) + list(_asset_dir(env).glob(f"{kind}-*")):
            if candidate.resolve() == target_path.resolve():
                continue
            if candidate.is_file():
                try:
                    candidate.unlink()
                except OSError:
                    pass

        file_storage.stream.seek(0)
        target_path.write_bytes(file_storage.stream.read())

        return {
            "url": FIXED_ASSET_ROUTES[kind],
            "filename": target_name,
            "content_type": content_type,
            "size": target_path.stat().st_size,
        }

    def resolve_asset(self, relative_path, env=None):
        relative_path = str(relative_path or "").strip("/")
        if relative_path == "":
            raise FileNotFoundError("asset 경로가 비어 있습니다.")
        if relative_path in FIXED_ASSET_ROUTES:
            target_path = _fixed_asset_path(relative_path, env=env) or _default_asset_path(relative_path)
            if target_path is None or target_path.is_file() is not True:
                raise FileNotFoundError("asset 파일을 찾을 수 없습니다.")
        else:
            base_dir = _asset_dir(env).resolve()
            target_path = (base_dir / relative_path).resolve()
            if target_path != base_dir and base_dir not in target_path.parents:
                raise FileNotFoundError("허용되지 않는 asset 경로입니다.")
            if not target_path.is_file():
                raise FileNotFoundError("asset 파일을 찾을 수 없습니다.")
        content_type = mimetypes.guess_type(target_path.name)[0] or "application/octet-stream"
        return {
            "path": str(target_path),
            "content_type": content_type,
            "filename": target_path.name,
            "size": os.path.getsize(target_path),
        }


Model = Appearance()
