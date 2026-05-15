import datetime
import hashlib
import hmac
import secrets

from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect


PASSWORD_KEY = "operator"
HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260000
SESSION_TTL_SECONDS = 60 * 60 * 12
RATE_LIMIT_WINDOW_SECONDS = 60 * 15
RATE_LIMIT_LOCK_SECONDS = 60 * 15
RATE_LIMIT_MAX_FAILURES = 5


class AuthError(Exception):
    def __init__(self, status_code, message, error_code, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.extra = extra


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def hash_password(password, salt=None, iterations=HASH_ITERATIONS):
    if password is None:
        raise ValueError("password is required")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"{HASH_ALGORITHM}${iterations}${salt}${digest.hex()}"


def verify_password(password, password_hash):
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False
        actual = hash_password(password or "", salt=salt, iterations=int(iterations)).split("$", 3)[3]
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public_session(row):
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "actor": "operator",
        "authenticated": row["revoked_at"] is None and row["expires_at"] > utcnow(),
        "expires_at": row["expires_at"],
        "last_seen_at": row["last_seen_at"],
        "created_at": row["created_at"],
    }


class AuthService:
    AuthError = AuthError
    token_hash = staticmethod(token_hash)

    def get_password_hash(self, connection):
        with connection.cursor() as cursor:
            cursor.execute("SELECT password_hash FROM operator_auth WHERE singleton_key = %s", (PASSWORD_KEY,))
            row = cursor.fetchone()
            return None if row is None else row["password_hash"]

    def has_password(self, env=None):
        with connect(env=env) as connection:
            return self.get_password_hash(connection) is not None

    def set_password(self, password, test_run_id=None, metadata=None, connection=None, env=None):
        if not password:
            raise AuthError(400, "비밀번호를 입력해주세요.", "PASSWORD_REQUIRED")
        if len(password) < 8:
            raise AuthError(400, "비밀번호는 8자 이상이어야 합니다.", "PASSWORD_TOO_SHORT")

        metadata = metadata or {}
        password_hash = hash_password(password)

        def write(conn):
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO operator_auth(singleton_key, password_hash, password_changed_at, test_run_id, metadata)
                    VALUES (%s, %s, now(), %s, %s)
                    ON CONFLICT (singleton_key) DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        password_changed_at = now(),
                        test_run_id = EXCLUDED.test_run_id,
                        metadata = EXCLUDED.metadata
                    RETURNING singleton_key, password_changed_at, test_run_id, metadata, created_at, updated_at
                    """,
                    (PASSWORD_KEY, password_hash, test_run_id, Jsonb(metadata)),
                )
                return cursor.fetchone()

        if connection is not None:
            return write(connection)
        with connect(env=env) as conn:
            return write(conn)

    def change_password(
        self,
        current_password,
        new_password,
        confirm_password=None,
        test_run_id=None,
        metadata=None,
        env=None,
    ):
        if not current_password:
            raise AuthError(400, "현재 비밀번호를 입력해주세요.", "CURRENT_PASSWORD_REQUIRED")
        if confirm_password is not None and new_password != confirm_password:
            raise AuthError(400, "새 비밀번호 확인이 일치하지 않습니다.", "PASSWORD_CONFIRM_MISMATCH")

        with connect(env=env) as connection:
            stored_hash = self.get_password_hash(connection)
            if stored_hash is None:
                raise AuthError(423, "초기 설정을 먼저 완료해주세요.", "SETUP_REQUIRED")
            if not verify_password(current_password, stored_hash):
                raise AuthError(401, "현재 비밀번호가 올바르지 않습니다.", "INVALID_CURRENT_PASSWORD")

            return self.set_password(
                new_password,
                test_run_id=test_run_id,
                metadata={**(metadata or {}), "source": "system_general_password_change"},
                connection=connection,
            )

    def _scope(self, remote_addr):
        return remote_addr or "unknown"

    def _current_lock(self, cursor, scope, now):
        cursor.execute(
            """
            SELECT locked_until
            FROM auth_login_attempts
            WHERE scope = %s AND success = false AND locked_until IS NOT NULL AND locked_until > %s
            ORDER BY locked_until DESC
            LIMIT 1
            """,
            (scope, now),
        )
        row = cursor.fetchone()
        return None if row is None else row["locked_until"]

    def _record_attempt(self, cursor, scope, success, remote_addr, user_agent, test_run_id, now):
        locked_until = None
        if not success:
            window_start = now - datetime.timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
            cursor.execute(
                """
                SELECT count(*) AS failures
                FROM auth_login_attempts
                WHERE scope = %s AND success = false AND attempted_at >= %s
                """,
                (scope, window_start),
            )
            failures = cursor.fetchone()["failures"] + 1
            if failures >= RATE_LIMIT_MAX_FAILURES:
                locked_until = now + datetime.timedelta(seconds=RATE_LIMIT_LOCK_SECONDS)

        cursor.execute(
            """
            INSERT INTO auth_login_attempts(scope, success, locked_until, attempted_at, remote_addr, user_agent, test_run_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (scope, success, locked_until, now, remote_addr, user_agent, test_run_id),
        )
        if success:
            cursor.execute("DELETE FROM auth_login_attempts WHERE scope = %s AND success = false", (scope,))
        return locked_until

    def login(self, password, remote_addr=None, user_agent=None, test_run_id=None, env=None):
        if not password:
            raise AuthError(400, "비밀번호를 입력해주세요.", "PASSWORD_REQUIRED")

        now = utcnow()
        scope = self._scope(remote_addr)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                locked_until = self._current_lock(cursor, scope, now)
                if locked_until is not None:
                    retry_after = max(1, int((locked_until - now).total_seconds()))
                    raise AuthError(
                        429,
                        "로그인 실패가 반복되어 잠시 후 다시 시도해주세요.",
                        "AUTH_RATE_LIMITED",
                        retry_after_seconds=retry_after,
                        locked_until=locked_until,
                    )

                stored_hash = self.get_password_hash(connection)
                if stored_hash is None:
                    raise AuthError(423, "설치 마법사를 먼저 완료해주세요.", "SETUP_REQUIRED")

                if not verify_password(password, stored_hash):
                    locked_until = self._record_attempt(
                        cursor, scope, False, remote_addr, user_agent, test_run_id, now
                    )
                    connection.commit()
                    if locked_until is not None:
                        raise AuthError(
                            429,
                            "로그인 실패가 반복되어 잠시 후 다시 시도해주세요.",
                            "AUTH_RATE_LIMITED",
                            retry_after_seconds=RATE_LIMIT_LOCK_SECONDS,
                            locked_until=locked_until,
                        )
                    raise AuthError(401, "비밀번호가 올바르지 않습니다.", "INVALID_PASSWORD")

                self._record_attempt(cursor, scope, True, remote_addr, user_agent, test_run_id, now)
                token = secrets.token_urlsafe(32)
                expires_at = now + datetime.timedelta(seconds=SESSION_TTL_SECONDS)
                cursor.execute(
                    """
                    INSERT INTO auth_sessions(token_hash, expires_at, last_seen_at, remote_addr, user_agent, test_run_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (token_hash(token), expires_at, now, remote_addr, user_agent, test_run_id),
                )
                row = cursor.fetchone()
                return {
                    "session_token": token,
                    "session": _public_session(row),
                }

    def current_session(self, session_token, env=None):
        if not session_token:
            return {"authenticated": False, "session": None}
        now = utcnow()
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_sessions
                    SET last_seen_at = %s
                    WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > %s
                    RETURNING *
                    """,
                    (now, token_hash(session_token), now),
                )
                row = cursor.fetchone()
                return {"authenticated": row is not None, "session": _public_session(row)}

    def is_session_valid(self, session_token, env=None):
        return self.current_session(session_token, env=env)["authenticated"]

    def logout(self, session_token, env=None):
        if not session_token:
            return False
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = now()
                    WHERE token_hash = %s AND revoked_at IS NULL
                    RETURNING id
                    """,
                    (token_hash(session_token),),
                )
                return cursor.fetchone() is not None

    def delete_by_test_run_id(self, test_run_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM auth_sessions WHERE test_run_id = %s", (test_run_id,))
                sessions = cursor.rowcount
                cursor.execute("DELETE FROM auth_login_attempts WHERE test_run_id = %s", (test_run_id,))
                attempts = cursor.rowcount
                cursor.execute("DELETE FROM operator_auth WHERE test_run_id = %s", (test_run_id,))
                passwords = cursor.rowcount
                return {"sessions": sessions, "login_attempts": attempts, "passwords": passwords}


Model = AuthService()
