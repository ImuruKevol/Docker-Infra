import re

settings = wiz.model("struct/settings")
connect = wiz.model("db/postgres").connect
MASKED_SECRET = settings.MASKED_SECRET


def _secret_key(env=None):
    return settings.secret_key(env)


SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)(password|passphrase|token|api[_-]?token|private[_-]?key|secret)(\s*[:=]\s*)([\"']?)([^\s,\"']+)([\"']?)"
)
PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)


def _normalize_secret_values(values):
    normalized = []
    seen = set()
    for value in values or []:
        if value is None:
            continue
        text = str(value)
        if len(text) < 4 or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return sorted(normalized, key=len, reverse=True)


def secret_values_from_settings(connection=None, env=None):
    def read(conn):
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT pgp_sym_decrypt(decode(secret_enc, 'base64'), %s) AS secret_value
                FROM system_settings
                WHERE is_secret = true AND secret_enc IS NOT NULL
                """,
                (_secret_key(env),),
            )
            return _normalize_secret_values(row["secret_value"] for row in cursor.fetchall())

    if connection is not None:
        return read(connection)
    with connect(env=env) as conn:
        return read(conn)


def mask_text(text, secret_values=None, connection=None, env=None):
    if text is None:
        return ""

    masked = str(text)
    registry = []
    if connection is not None or env is not None:
        registry.extend(secret_values_from_settings(connection=connection, env=env))
    registry.extend(_normalize_secret_values(secret_values or []))

    for secret in _normalize_secret_values(registry):
        masked = masked.replace(secret, MASKED_SECRET)

    masked = PRIVATE_KEY_BLOCK_RE.sub(MASKED_SECRET, masked)
    masked = SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}{MASKED_SECRET}{match.group(5)}", masked)
    return masked


class SecretMasking:
    MASKED_SECRET = MASKED_SECRET
    secret_values_from_settings = staticmethod(secret_values_from_settings)
    mask_text = staticmethod(mask_text)


Model = SecretMasking()
