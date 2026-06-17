"""
사용자 인증 + 훈련 기록 저장 모듈
─────────────────────────────────
- 표준 라이브러리만 사용 (sqlite3 / hashlib / hmac / secrets)
- 비밀번호: pbkdf2-sha256 + per-user salt 로 해싱하여 저장 (평문 저장 X)
- 인증 토큰: HMAC 서명된 stateless 토큰 (세션 테이블 불필요)
"""
import sqlite3, hashlib, hmac, secrets, base64, json, time, os

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(BASE_DIR, "app.db")
SECRET_FILE = os.path.join(BASE_DIR, ".secret")

PBKDF2_ITERATIONS = 200_000
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 14   # 14일


# ── 서명 비밀키 (없으면 생성하여 파일에 보관 → 재시작해도 토큰 유지) ──
def _load_secret() -> bytes:
    env = os.getenv("SECRET_KEY")
    if env:
        return env.encode()
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "rb") as f:
            return f.read()
    key = secrets.token_bytes(32)
    with open(SECRET_FILE, "wb") as f:
        f.write(key)
    return key

_SECRET = _load_secret()


# ── DB ───────────────────────────────────────────────
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    UNIQUE NOT NULL,
                pw_hash    TEXT    NOT NULL,
                pw_salt    TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                scenario    TEXT    NOT NULL,
                difficulty  TEXT    NOT NULL,
                grade       TEXT    NOT NULL,
                score       INTEGER NOT NULL,
                feedback    TEXT,
                tip         TEXT,
                wrong_items TEXT,
                created_at  TEXT    NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        # 기존 DB 마이그레이션: 분석 리포트(JSON) 컬럼 추가
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(history)")]
        if "report_json" not in cols:
            conn.execute("ALTER TABLE history ADD COLUMN report_json TEXT")
    print(f"✅ DB 준비 완료: {DB_PATH}")


# ── 비밀번호 해싱 ─────────────────────────────────────
def _hash_pw(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex()


# ── 사용자 ────────────────────────────────────────────
class AuthError(Exception):
    pass


def create_user(username: str, password: str) -> dict:
    username = username.strip()
    if not username or not password:
        raise AuthError("아이디와 비밀번호를 입력해주세요.")
    if len(username) < 3:
        raise AuthError("아이디는 3자 이상이어야 합니다.")
    if len(password) < 4:
        raise AuthError("비밀번호는 4자 이상이어야 합니다.")

    salt = secrets.token_bytes(16)
    pw_hash = _hash_pw(password, salt)
    now = _now()
    try:
        with _conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, pw_hash, pw_salt, created_at) VALUES (?,?,?,?)",
                (username, pw_hash, salt.hex(), now),
            )
            return {"id": cur.lastrowid, "username": username}
    except sqlite3.IntegrityError:
        raise AuthError("이미 사용 중인 아이디입니다.")


def verify_user(username: str, password: str) -> dict:
    username = username.strip()
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, username, pw_hash, pw_salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        raise AuthError("아이디 또는 비밀번호가 올바르지 않습니다.")
    salt = bytes.fromhex(row["pw_salt"])
    if not hmac.compare_digest(_hash_pw(password, salt), row["pw_hash"]):
        raise AuthError("아이디 또는 비밀번호가 올바르지 않습니다.")
    return {"id": row["id"], "username": row["username"]}


def get_user(user_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


# ── 훈련 기록 ─────────────────────────────────────────
def add_history(user_id: int, item: dict) -> dict:
    now = _now()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO history
               (user_id, scenario, difficulty, grade, score, feedback, tip, wrong_items, report_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id,
                item.get("scenario", ""),
                item.get("difficulty", ""),
                item.get("grade", ""),
                int(item.get("score", 0)),
                item.get("feedback", ""),
                item.get("tip", ""),
                json.dumps(item.get("wrong_items", []), ensure_ascii=False),
                json.dumps(item.get("report_json"), ensure_ascii=False) if item.get("report_json") else None,
                now,
            ),
        )
        rid = cur.lastrowid
    return _history_row_to_dict_by_id(rid)


def get_history(user_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 100",
            (user_id,),
        ).fetchall()
    return [_row_to_history(r) for r in rows]


def _history_row_to_dict_by_id(rid: int) -> dict:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM history WHERE id = ?", (rid,)).fetchone()
    return _row_to_history(row)


def _row_to_history(r: sqlite3.Row) -> dict:
    keys = r.keys()
    report_raw = r["report_json"] if "report_json" in keys else None
    return {
        "id":         r["id"],
        "scenario":   r["scenario"],
        "difficulty": r["difficulty"],
        "grade":      r["grade"],
        "score":      r["score"],
        "feedback":   r["feedback"] or "",
        "tip":        r["tip"] or "",
        "wrong_items": json.loads(r["wrong_items"] or "[]"),
        "report":     json.loads(report_raw) if report_raw else None,
        "date":       r["created_at"][:10],
        "created_at": r["created_at"],
    }


# ── 토큰 (HMAC 서명) ──────────────────────────────────
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user_id: int) -> str:
    payload = {"uid": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def parse_token(token: str) -> int | None:
    try:
        body, sig = token.split(".")
        expected = _b64(hmac.new(_SECRET, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64d(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return int(payload["uid"])
    except Exception:
        return None


def _now() -> str:
    # ISO 형식 (로컬 시간)
    return time.strftime("%Y-%m-%d %H:%M:%S")
