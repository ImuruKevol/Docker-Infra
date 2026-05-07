import datetime
import decimal
import json
import uuid


class TemplateError(Exception):
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


def json_text(value):
    return json.dumps(value or {}, ensure_ascii=False, indent=2) + "\n"


class TemplatesShared:
    TemplateError = TemplateError
    serialize = staticmethod(serialize)
    row = staticmethod(row)
    json_text = staticmethod(json_text)


Model = TemplatesShared()
