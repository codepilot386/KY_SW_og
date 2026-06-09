from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

from google import genai
from google.genai import types

from dotenv import load_dotenv
from typecast import Typecast
from typecast.models import TTSRequest, SmartPrompt, Output

from passlib.context import CryptContext

import os
import io
import re
import json
import uuid
import random
import sqlite3
import traceback
import hashlib
from pathlib import Path
from datetime import datetime


# =========================
# 환경 변수
# =========================

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
DB_PATH = BASE_DIR / "app.db"

load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

TYPECAST_API_KEY = os.getenv("TYPECAST_API_KEY")
TYPECAST_VOICE_ID = os.getenv("TYPECAST_VOICE_ID")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
tts_client = Typecast(api_key=TYPECAST_API_KEY) if TYPECAST_API_KEY else None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def prepare_password(password: str) -> str:
    """
    bcrypt의 72 bytes 제한을 피하기 위해
    SHA-256으로 먼저 고정 길이 문자열을 만든 뒤 bcrypt에 넣는다.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# =========================
# DB
# =========================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        scenario_type TEXT NOT NULL,
        score INTEGER NOT NULL,
        result_label TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================
# FastAPI
# =========================

app = FastAPI(title="Voice Phishing Training API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# 요청 모델
# =========================

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRequest(BaseModel):
    token: str


class ScoreSaveRequest(BaseModel):
    token: str
    scenario_type: str
    score: int


class AdminUserUpdateRequest(BaseModel):
    token: str
    user_id: int
    username: str | None = None
    password: str | None = None


class AdminUserDeleteRequest(BaseModel):
    token: str
    user_id: int


class AdminScoreDeleteRequest(BaseModel):
    token: str
    score_id: int


class StartRequest(BaseModel):
    scenario_type: str = "agency"


class ChatRequest(BaseModel):
    previous_message: str = ""
    user_response: str = ""
    turn_count: int = 1
    answer_index: int | None = None
    scenario_type: str = "agency"


class TTSRequestBody(BaseModel):
    text: str
    style: str = "neutral"


# =========================
# 사용자 / 점수 함수
# =========================

def get_user_by_token(token: str):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT users.id, users.username
    FROM sessions
    JOIN users ON sessions.user_id = users.id
    WHERE sessions.token = ?
    """, (token,))

    user = cur.fetchone()
    conn.close()

    if not user:
        return None

    return {
        "id": user["id"],
        "username": user["username"]
    }


def require_admin(token: str):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    if user["username"] != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    return user


def scenario_name(scenario_type: str):
    names = {
        "agency": "기관 사칭 훈련",
        "acquaintance": "지인 사칭 훈련",
        "loan": "대출 사기형 훈련",
    }
    return names.get(scenario_type, "기타 훈련")


def result_label(score: int):
    if score >= 80:
        return "안전"
    if score >= 50:
        return "주의"
    return "위험"


# =========================
# Gemini 프롬프트
# =========================

SAFETY_INSTRUCTION = """
너는 보이스피싱 예방 교육용 가상 통화 시뮬레이터다.

목표:
사용자가 실제 전화나 문자처럼 느끼면서도 사기 징후를 안전하게 식별하고 대응하도록 훈련한다.

규칙:
- 상황 설명이 아니라 상대방이 직접 말하는 실제 통화 대사처럼 작성한다.
- message는 1~2문장으로 짧게 작성한다.
- 계좌번호, 카드번호, 인증번호, 비밀번호, 주민등록번호, 송금 요구 문구는 절대 작성하지 않는다.
- 실제 범죄에 악용될 수 있는 구체적인 사칭 절차는 만들지 않는다.
- 사용자가 고를 수 있는 선택지 4개를 만든다.
- 선택지 중 하나는 반드시 안전한 대응이어야 한다.
- 응답은 반드시 JSON 하나만 출력한다.

JSON 형식:
{
  "message": "상대방 대사",
  "choices": ["선택지1", "선택지2", "선택지3", "선택지4"],
  "answer_index": 0,
  "feedback": "왜 이 선택이 안전한지 설명",
  "tts_style": "neutral"
}

tts_style 값:
neutral, friendly, urgent, pressure, calm, feedback
"""


# =========================
# fallback 시나리오
# =========================

FALLBACK_SCENES = {
    "agency": [
        {
            "message": "여보세요? 본인 확인 관련해서 연락드렸습니다. 잠시 통화 가능하신가요?",
            "choices": [
                "어떤 기관인지 확인하고 공식 번호로 다시 연락하겠다고 말한다.",
                "바로 본인 확인을 진행하겠다고 말한다.",
                "상대방 말을 계속 듣는다.",
                "이름과 소속을 물어본 뒤 계속 통화한다."
            ],
            "answer_index": 0,
            "feedback": "낯선 연락은 상대방이 알려준 번호가 아니라 공식 대표번호로 직접 확인하는 것이 안전합니다.",
            "tts_style": "neutral"
        },
        {
            "message": "확인이 늦어지면 불이익이 생길 수 있습니다. 지금 바로 확인해주셔야 합니다.",
            "choices": [
                "급하다고 하니 바로 응답한다.",
                "개인정보는 말하지 않고 통화를 종료한 뒤 공식 번호로 확인한다.",
                "상대방에게 더 자세히 설명해달라고 한다.",
                "상대방이 안내하는 방식대로 진행한다."
            ],
            "answer_index": 1,
            "feedback": "급하게 압박하는 연락은 보이스피싱의 흔한 특징입니다. 통화를 끊고 공식 경로로 확인해야 합니다.",
            "tts_style": "pressure"
        }
    ],
    "acquaintance": [
        {
            "message": "나야. 지금 휴대폰이 고장 나서 다른 번호로 연락했어. 잠깐 확인 좀 해줄 수 있어?",
            "choices": [
                "바로 상대방 말을 믿고 도와준다.",
                "원래 알고 있던 번호로 직접 전화해서 확인한다.",
                "무슨 일인지 자세히 물어본다.",
                "상대방이 보내는 링크를 눌러 확인한다."
            ],
            "answer_index": 1,
            "feedback": "지인 사칭은 원래 알고 있던 번호로 직접 확인하는 것이 가장 안전합니다.",
            "tts_style": "friendly"
        },
        {
            "message": "지금 상황이 급해서 그런데, 잠깐만 내 말대로 해줄 수 있어?",
            "choices": [
                "급하다고 하니 바로 따른다.",
                "상대방 신원을 원래 연락처로 먼저 확인한다.",
                "일단 어떤 일인지 계속 대화한다.",
                "상대방이 보내는 안내를 따른다."
            ],
            "answer_index": 1,
            "feedback": "급한 부탁이어도 지인 여부를 직접 확인하기 전에는 행동하지 않아야 합니다.",
            "tts_style": "urgent"
        }
    ],
    "loan": [
        {
            "message": "고객님, 대출 승인 가능 대상으로 확인되어 연락드렸습니다. 지금 진행하면 좋은 조건으로 안내 가능합니다.",
            "choices": [
                "바로 상담을 진행한다.",
                "상대방이 알려주는 링크로 접속한다.",
                "공식 금융기관 앱이나 홈페이지에서 직접 확인한다.",
                "상대방에게 필요한 절차를 물어본다."
            ],
            "answer_index": 2,
            "feedback": "대출 관련 연락은 반드시 공식 금융기관 앱, 홈페이지, 대표번호로 직접 확인해야 합니다.",
            "tts_style": "friendly"
        },
        {
            "message": "오늘 안에 확인하셔야 조건이 유지됩니다. 지금 간단히 진행 도와드릴게요.",
            "choices": [
                "조건이 좋으니 바로 진행한다.",
                "급하게 결정하지 않고 공식 채널로 직접 확인한다.",
                "상대방에게 더 좋은 조건이 있는지 묻는다.",
                "상대방이 요구하는 절차를 따른다."
            ],
            "answer_index": 1,
            "feedback": "당일 마감이나 급한 결정을 유도하는 말은 의심해야 합니다. 공식 채널로 직접 확인하세요.",
            "tts_style": "pressure"
        }
    ]
}


def fallback_scene(scenario_type: str = "agency"):
    scenes = FALLBACK_SCENES.get(scenario_type, FALLBACK_SCENES["agency"])
    return random.choice(scenes)


# =========================
# Gemini 처리
# =========================

def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("JSON을 찾지 못했습니다.")

    return json.loads(match.group(0))


def normalize_scene(data: dict) -> dict:
    choices = data.get("choices", [])
    answer_index = data.get("answer_index", 0)
    tts_style = data.get("tts_style", "neutral")

    allowed_styles = ["neutral", "friendly", "urgent", "pressure", "calm", "feedback"]

    if not isinstance(choices, list):
        choices = []

    if tts_style not in allowed_styles:
        tts_style = "neutral"

    if not isinstance(answer_index, int) or answer_index < 0 or answer_index >= len(choices):
        answer_index = 0 if choices else -1

    return {
        "message": data.get("message", "훈련 상황을 불러오지 못했습니다."),
        "choices": choices[:4],
        "answer_index": answer_index,
        "feedback": data.get("feedback", "안전한 대응을 선택하는 것이 중요합니다."),
        "tts_style": tts_style,
    }


def generate_scene(prompt: str, scenario_type: str) -> dict:
    if not gemini_client:
        return fallback_scene(scenario_type)

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )

        return normalize_scene(extract_json(response.text))

    except Exception as e:
        print("Gemini error:", repr(e))
        traceback.print_exc()
        return fallback_scene(scenario_type)


# =========================
# TTS 스타일
# =========================

def get_tts_style(style: str) -> dict:
    styles = {
        "neutral": {
            "tempo": 1.0,
            "pitch": 1,
            "previous_text": "상대방은 평범하게 전화를 시작합니다.",
            "next_text": "사용자는 신중하게 대응해야 합니다."
        },
        "friendly": {
            "tempo": 1.0,
            "pitch": 1,
            "previous_text": "상대방은 친절하게 안내합니다.",
            "next_text": "사용자는 내용을 확인합니다."
        },
        "urgent": {
            "tempo": 1.08,
            "pitch": 1,
            "previous_text": "상대방은 조금 급하게 말합니다.",
            "next_text": "사용자는 급하게 판단하지 않아야 합니다."
        },
        "pressure": {
            "tempo": 1.12,
            "pitch": 0,
            "previous_text": "상대방은 압박하듯 말합니다.",
            "next_text": "사용자는 개인정보를 말하지 않아야 합니다."
        },
        "calm": {
            "tempo": 0.95,
            "pitch": 0,
            "previous_text": "상황이 정리되고 있습니다.",
            "next_text": "사용자는 공식 경로로 확인합니다."
        },
        "feedback": {
            "tempo": 0.98,
            "pitch": 1,
            "previous_text": "훈련 피드백을 안내합니다.",
            "next_text": "사용자는 안전 수칙을 기억합니다."
        }
    }

    return styles.get(style, styles["neutral"])


# =========================
# 기본 API
# =========================

@app.get("/api/health")
def health():
    return {"status": "ok"}


# =========================
# 로그인 / 회원가입 API
# =========================

@app.post("/api/register")
def register(req: RegisterRequest):
    username = req.username.strip()
    password = req.password.strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="아이디와 비밀번호를 입력하세요.")

    if len(password) < 4:
        raise HTTPException(status_code=400, detail="비밀번호는 4자 이상이어야 합니다.")

    conn = get_db()
    cur = conn.cursor()

    try:
        password_hash = pwd_context.hash(prepare_password(password))

        cur.execute(
            """
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, datetime.now().isoformat())
        )

        conn.commit()

    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="이미 존재하는 아이디입니다.")

    finally:
        conn.close()

    return {"message": "회원가입 성공"}


@app.post("/api/login")
def login(req: LoginRequest):
    username = req.username.strip()
    password = req.password.strip()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    if not pwd_context.verify(prepare_password(password), user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    token = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO sessions (token, user_id, created_at)
        VALUES (?, ?, ?)
        """,
        (token, user["id"], datetime.now().isoformat())
    )

    conn.commit()
    conn.close()

    return {
        "message": "로그인 성공",
        "token": token,
        "username": user["username"]
    }


@app.post("/api/logout")
def logout(req: TokenRequest):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM sessions WHERE token = ?", (req.token,))
    conn.commit()
    conn.close()

    return {"message": "로그아웃 완료"}


@app.post("/api/scores")
def get_scores(req: TokenRequest):
    user = get_user_by_token(req.token)

    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT scenario_type, score, result_label, created_at
        FROM training_scores
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (user["id"],)
    )

    rows = cur.fetchall()
    conn.close()

    scores = []

    for row in rows:
        scores.append({
            "scenario_type": row["scenario_type"],
            "scenario_name": scenario_name(row["scenario_type"]),
            "score": row["score"],
            "result_label": row["result_label"],
            "created_at": row["created_at"]
        })

    return {"scores": scores}


@app.post("/api/save-score")
def save_score(req: ScoreSaveRequest):
    user = get_user_by_token(req.token)

    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    label = result_label(req.score)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO training_scores (
            user_id,
            scenario_type,
            score,
            result_label,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user["id"],
            req.scenario_type,
            req.score,
            label,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()

    return {
        "message": "점수 저장 완료",
        "score": req.score,
        "result_label": label
    }


# =========================
# 관리자 API
# =========================

@app.post("/api/admin/users")
def admin_get_users(req: TokenRequest):
    require_admin(req.token)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        users.id,
        users.username,
        users.created_at,
        COUNT(training_scores.id) AS training_count,
        COALESCE(AVG(training_scores.score), 0) AS avg_score
    FROM users
    LEFT JOIN training_scores ON users.id = training_scores.user_id
    GROUP BY users.id
    ORDER BY users.created_at DESC
    """)

    rows = cur.fetchall()
    conn.close()

    users = []

    for row in rows:
        users.append({
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
            "training_count": row["training_count"],
            "avg_score": round(row["avg_score"], 1)
        })

    return {"users": users}


@app.post("/api/admin/scores")
def admin_get_scores(req: TokenRequest):
    require_admin(req.token)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        training_scores.id,
        users.username,
        training_scores.scenario_type,
        training_scores.score,
        training_scores.result_label,
        training_scores.created_at
    FROM training_scores
    JOIN users ON training_scores.user_id = users.id
    ORDER BY training_scores.created_at DESC
    LIMIT 100
    """)

    rows = cur.fetchall()
    conn.close()

    scores = []

    for row in rows:
        scores.append({
            "id": row["id"],
            "username": row["username"],
            "scenario_type": row["scenario_type"],
            "scenario_name": scenario_name(row["scenario_type"]),
            "score": row["score"],
            "result_label": row["result_label"],
            "created_at": row["created_at"]
        })

    return {"scores": scores}


@app.post("/api/admin/update-user")
def admin_update_user(req: AdminUserUpdateRequest):
    require_admin(req.token)

    new_username = req.username.strip() if req.username else None
    new_password = req.password.strip() if req.password else None

    if not new_username and not new_password:
        raise HTTPException(status_code=400, detail="수정할 값이 없습니다.")

    if new_password and len(new_password) < 4:
        raise HTTPException(status_code=400, detail="비밀번호는 4자 이상이어야 합니다.")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (req.user_id,))
    target = cur.fetchone()

    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    try:
        if new_username:
            cur.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (new_username, req.user_id)
            )

        if new_password:
            password_hash = pwd_context.hash(prepare_password(new_password))
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, req.user_id)
            )

        conn.commit()

    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="이미 존재하는 아이디입니다.")

    finally:
        conn.close()

    return {"message": "사용자 정보 수정 완료"}


@app.post("/api/admin/delete-user")
def admin_delete_user(req: AdminUserDeleteRequest):
    admin_user = require_admin(req.token)

    if admin_user["id"] == req.user_id:
        raise HTTPException(status_code=400, detail="관리자 본인은 삭제할 수 없습니다.")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (req.user_id,))
    target = cur.fetchone()

    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    cur.execute("DELETE FROM training_scores WHERE user_id = ?", (req.user_id,))
    cur.execute("DELETE FROM sessions WHERE user_id = ?", (req.user_id,))
    cur.execute("DELETE FROM users WHERE id = ?", (req.user_id,))

    conn.commit()
    conn.close()

    return {"message": "사용자 삭제 완료"}


@app.post("/api/admin/delete-score")
def admin_delete_score(req: AdminScoreDeleteRequest):
    require_admin(req.token)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM training_scores WHERE id = ?", (req.score_id,))
    target = cur.fetchone()

    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="훈련 기록을 찾을 수 없습니다.")

    cur.execute("DELETE FROM training_scores WHERE id = ?", (req.score_id,))

    conn.commit()
    conn.close()

    return {"message": "점수 기록 삭제 완료"}


# =========================
# 훈련 API
# =========================

@app.post("/api/start")
def start_training(req: StartRequest):
    scenario_map = {
        "agency": "검찰, 경찰, 금융기관 등을 사칭하는 보이스피싱 통화",
        "acquaintance": "가족, 친구, 지인 등을 사칭하는 메신저 또는 전화",
        "loan": "저금리 대출, 승인 안내, 수수료 등을 미끼로 한 대출 사기"
    }

    scenario_desc = scenario_map.get(req.scenario_type, scenario_map["agency"])

    prompt = SAFETY_INSTRUCTION + f"""
훈련 유형:
{scenario_desc}

첫 번째 통화 장면을 시작한다.
상황 설명 없이 상대방의 첫 대사처럼 작성한다.
선택지 4개를 만든다.
그중 하나는 안전한 대응이어야 한다.
"""

    scene = generate_scene(prompt, req.scenario_type)

    return {
        **scene,
        "is_finished": False
    }


@app.post("/api/chat")
def continue_training(req: ChatRequest):
    if req.turn_count >= 10:
        return {
            "is_finished": True,
            "report": {
                "feedback": "훈련이 종료되었습니다. 낯선 연락은 즉시 끊고 공식 번호로 직접 확인하는 습관이 중요합니다.",
                "tip": "개인정보, 인증번호, 송금 요구가 나오면 바로 의심하세요."
            }
        }

    prompt = SAFETY_INSTRUCTION + f"""
이전 상대방 대사:
{req.previous_message}

사용자 응답:
{req.user_response}

현재 훈련 유형:
{req.scenario_type}

현재 턴:
{req.turn_count}

이어서 실제 통화가 계속되는 것처럼 다음 상대방 대사를 작성한다.
상황 설명이 아니라 상대방이 직접 말하는 대사로 작성한다.
선택지 4개를 만든다.
그중 하나는 안전한 대응이어야 한다.
"""

    scene = generate_scene(prompt, req.scenario_type)

    return {
        **scene,
        "is_finished": False
    }


@app.post("/api/tts")
def text_to_speech(req: TTSRequestBody):
    if not tts_client:
        raise HTTPException(status_code=500, detail="TYPECAST_API_KEY가 없습니다.")

    if not TYPECAST_VOICE_ID:
        raise HTTPException(status_code=500, detail="TYPECAST_VOICE_ID가 없습니다.")

    if not req.text.strip():
        raise HTTPException(status_code=400, detail="읽을 문장이 없습니다.")

    try:
        style_config = get_tts_style(req.style)

        response = tts_client.text_to_speech(
            TTSRequest(
                text=req.text,
                model="ssfm-v30",
                voice_id=TYPECAST_VOICE_ID,
                prompt=SmartPrompt(
                    emotion_type="smart",
                    previous_text=style_config["previous_text"],
                    next_text=style_config["next_text"]
                ),
                output=Output(
                    audio_format="mp3",
                    audio_tempo=style_config["tempo"],
                    audio_pitch=style_config["pitch"],
                    volume=100
                )
            )
        )

        return StreamingResponse(
            io.BytesIO(response.audio_data),
            media_type="audio/mpeg"
        )

    except Exception as e:
        print("Typecast error:", repr(e))
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Typecast TTS 실패: {repr(e)}"
        )
# =========================
# React 프론트엔드 제공
# =========================

FRONTEND_DIR = BASE_DIR / "static"
ASSETS_DIR = FRONTEND_DIR / "assets"

if ASSETS_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=ASSETS_DIR),
        name="assets"
    )


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API를 찾을 수 없습니다.")

    requested_file = FRONTEND_DIR / full_path

    if full_path and requested_file.exists() and requested_file.is_file():
        return FileResponse(requested_file)

    index_file = FRONTEND_DIR / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    raise HTTPException(
        status_code=404,
        detail="프론트엔드 빌드 파일을 찾을 수 없습니다."
    )

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)