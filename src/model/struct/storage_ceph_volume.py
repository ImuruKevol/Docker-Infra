import json


def _json_object(text):
    text = str(text or "")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return {}


class StorageCephVolume:
    def lvm_artifact(self, stdout, osd_id):
        data = _json_object(stdout)
        items = data.get(str(osd_id)) or []
        if not items:
            return {}
        return items[0] or {}

    def osd_fsid(self, artifact):
        return str(((artifact or {}).get("tags") or {}).get("ceph.osd_fsid") or "")

    def device_path(self, artifact):
        return str((artifact or {}).get("path") or (artifact or {}).get("lv_path") or "")

    def device_uuid(self, artifact):
        return str((artifact or {}).get("lv_uuid") or "")


Model = StorageCephVolume()
