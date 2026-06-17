from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import google.generativeai as genai
import httpx, asyncio, os, json, sys
from dotenv import load_dotenv

import auth

# 한글 Windows(cp949) 콘솔에서도 이모지 로그가 깨지거나 startup이 죽지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

TYPECAST_API_KEY = os.getenv("TYPECAST_API_KEY", "")
TYPECAST_ACTOR_ID = os.getenv("TYPECAST_ACTOR_ID", "")   # 직접 지정 시 사용
_actor_id_cache: str | None = None                         # 자동 감지된 actor_id

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

safety_settings = {
    'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
    'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
}

# ── Typecast 시작 시 actor 자동 감지 ─────────────────
@app.on_event("startup")
async def init_typecast():
    global _actor_id_cache

    # 사용자/기록 DB 초기화
    auth.init_db()

    # .env에 직접 지정한 경우 바로 사용
    if TYPECAST_ACTOR_ID:
        _actor_id_cache = TYPECAST_ACTOR_ID
        print(f"✅ Typecast actor (env): {_actor_id_cache}")
        return

    if not TYPECAST_API_KEY:
        print("⚠️  TYPECAST_API_KEY 없음 → 브라우저 TTS 사용")
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                "https://typecast.ai/api/actor",
                headers={"Authorization": f"Bearer {TYPECAST_API_KEY}"},
            )
            actors = res.json().get("result", [])
            print(f"📢 사용 가능한 Typecast actor: {len(actors)}개")

            # 한국어 남성(중저음) 우선 선택
            PREFER_KEYWORDS = ["수사", "아나운서", "뉴스", "공식", "남성", "남자",
                               "범수", "진우", "민준", "재원"]

            chosen = None
            for kw in PREFER_KEYWORDS:
                for a in actors:
                    name_ko = a.get("name", {}).get("ko", "")
                    if kw in name_ko:
                        chosen = a
                        break
                if chosen:
                    break

            # 키워드 미매칭 → 첫 번째 actor 사용
            if not chosen and actors:
                chosen = actors[0]

            if chosen:
                _actor_id_cache = chosen.get("actor_id", "")
                name = chosen.get("name", {}).get("ko", "?")
                print(f"✅ Typecast actor 선택: '{name}' ({_actor_id_cache})")
            else:
                print("⚠️  Typecast actor를 찾을 수 없음")
    except Exception as e:
        print(f"⚠️  Typecast 초기화 실패: {e}")


# ── 시나리오별 설정 ─────────────────────────────────
SCENARIO_CONTEXT = {
    'prosecutor': '서울중앙지검 수사관 또는 검사를 사칭. 피의자 명의 계좌 개설, 대포통장 연루, 국가보안법 위반 혐의로 수사 중이라고 협박. 구속 영장, 재산 동결을 빌미로 압박.',
    'bank':       '금융감독원 직원 또는 시중은행 보안팀을 사칭. 명의도용 의심, 대출사기 연루, 계좌 이상거래 등을 빌미로 "안전 계좌"로 돈을 이체하거나 OTP·보안카드 정보를 요구.',
    'delivery':   '택배회사 고객센터 또는 관세청 직원을 사칭. 해외 발송 미수령 택배, 관세 미납, 개인정보 도용 의심을 빌미로 앱 설치·개인정보 입력을 유도.',
    'acquaintance':'피해자의 자녀·부모·친구를 사칭. 교통사고 발생, 교도소 수감, 긴급 수술비 필요 등 위급 상황을 연출하여 빠른 계좌이체를 요구.',
}

DIFFICULTY_INSTRUCTION = {
    'easy':   '선택지를 비교적 명확하게 구성. 오답은 명백히 위험한 행동, 정답은 직관적인 안전 행동.',
    'medium': '오답이 "합리적인 확인 절차"처럼 보이게 교묘하게 작성. 정답은 단호한 차단 행동.',
    'hard':   '오답이 매우 그럴듯하고 안전해 보이도록 극도로 교묘하게 작성. 사기꾼 대사에 시간 압박("지금 당장!", "30초 안에!")을 반드시 포함.',
}

# ── Models ──────────────────────────────────────────
class StartRequest(BaseModel):
    scenario:   str = 'prosecutor'
    difficulty: str = 'medium'

class ChatRequest(BaseModel):
    previous_message: str
    user_response:    str
    turn_count:       int
    scenario:         str = 'prosecutor'
    difficulty:       str = 'medium'

class TTSRequest(BaseModel):
    text: str

class AuthRequest(BaseModel):
    username: str
    password: str

class HistoryItem(BaseModel):
    scenario:    str = ''
    difficulty:  str = ''
    grade:       str = ''
    score:       int = 0
    feedback:    str = ''
    tip:         str = ''
    wrong_items: list = []
    report_json: dict | None = None

class TurnRecord(BaseModel):
    turn:           int
    scammer_message: str = ''
    user_choice:    str = ''
    is_correct:     bool = False
    correct_answer: str = ''

class AnalyzeRequest(BaseModel):
    scenario:   str = 'prosecutor'
    difficulty: str = 'medium'
    transcript: list[TurnRecord] = []


# ── 인증 헬퍼 ────────────────────────────────────────
def require_user(authorization: str | None) -> int:
    """Authorization: Bearer <token> 헤더에서 user_id를 추출. 실패 시 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    user_id = auth.parse_token(authorization[7:])
    if user_id is None:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다. 다시 로그인해주세요.")
    return user_id


# ── /api/auth/register ───────────────────────────────
@app.post("/api/auth/register")
async def register(req: AuthRequest):
    try:
        user = auth.create_user(req.username, req.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"token": auth.make_token(user["id"]), "user": user}


# ── /api/auth/login ──────────────────────────────────
@app.post("/api/auth/login")
async def login(req: AuthRequest):
    try:
        user = auth.verify_user(req.username, req.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": auth.make_token(user["id"]), "user": user}


# ── /api/me ──────────────────────────────────────────
@app.get("/api/me")
async def me(authorization: str | None = Header(default=None)):
    user_id = require_user(authorization)
    user = auth.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    return {"user": user}


# ── /api/history ─────────────────────────────────────
@app.get("/api/history")
async def list_history(authorization: str | None = Header(default=None)):
    user_id = require_user(authorization)
    return {"history": auth.get_history(user_id)}


@app.post("/api/history")
async def create_history(item: HistoryItem, authorization: str | None = Header(default=None)):
    user_id = require_user(authorization)
    saved = auth.add_history(user_id, item.model_dump())
    return {"item": saved}


# ── /api/tts  (Typecast 프록시) ──────────────────────
@app.post("/api/tts")
async def tts_proxy(req: TTSRequest):
    """
    Typecast API를 통해 고품질 한국어 TTS를 반환한다.
    API 키가 없거나 실패 시 503을 반환 → 프론트엔드가 Web Speech API로 폴백.
    """
    actor_id = _actor_id_cache

    if not TYPECAST_API_KEY or not actor_id:
        return Response(status_code=503, content=b"")

    text = req.text[:350]   # Typecast 350자 제한

    try:
        async with httpx.AsyncClient(timeout=20) as client:

            # ① 합성 요청 (비동기 방식 → speak_v2_url 반환)
            speak_res = await client.post(
                "https://typecast.ai/api/speak",
                headers={
                    "Authorization": f"Bearer {TYPECAST_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "text":              text,
                    "tts_mode":          "actor",
                    "actor_id":          actor_id,
                    "lang":              "ko-kr",
                    "xapi_hd":           True,
                    "xapi_audio_format": "mp3",
                    "speed_x":           1.0,
                },
            )

            if speak_res.status_code != 200:
                print(f"⚠️  Typecast speak 오류 {speak_res.status_code}: {speak_res.text[:200]}")
                return Response(status_code=503, content=b"")

            speak_v2_url = speak_res.json()["result"]["speak_v2_url"]

            # ② 폴링 (최대 15초, 0.5초 간격)
            for _ in range(30):
                await asyncio.sleep(0.5)
                poll = await client.get(
                    speak_v2_url,
                    headers={"Authorization": f"Bearer {TYPECAST_API_KEY}"},
                )
                result = poll.json().get("result", {})
                status = result.get("status")

                if status == "done":
                    audio_url = result.get("audio_download_url", "")
                    if not audio_url:
                        return Response(status_code=503, content=b"")
                    audio = await client.get(audio_url)
                    return Response(
                        content=audio.content,
                        media_type="audio/mpeg",
                        headers={"Cache-Control": "no-cache"},
                    )
                elif status == "error":
                    print("⚠️  Typecast 합성 오류")
                    return Response(status_code=503, content=b"")

            # 타임아웃
            return Response(status_code=504, content=b"")

    except Exception as e:
        print(f"⚠️  Typecast TTS 예외: {e}")
        return Response(status_code=503, content=b"")


# ── /api/start ──────────────────────────────────────
@app.post("/api/start")
async def start_training(req: StartRequest):
    try:
        sc_ctx   = SCENARIO_CONTEXT.get(req.scenario, SCENARIO_CONTEXT['prosecutor'])
        diff_ins = DIFFICULTY_INSTRUCTION.get(req.difficulty, DIFFICULTY_INSTRUCTION['medium'])

        prompt = f"""
너는 보이스피싱 훈련 시뮬레이터야. 아래 설정에 맞는 첫 번째 사기 대사와 선택지를 생성해.

[시나리오]
{sc_ctx}

[난이도 지침]
{diff_ins}

[필수 규칙]
- 선택지 4개 (정답 1~2개, 오답 2~3개)
- 오답: 피해자가 "안전한 대처"라고 착각하게 만드는 함정
- 정답: 실제로 가장 현명하고 안전한 행동
- 사기꾼 대사는 실감나고 위협적으로, 50~100자 내외
- 반드시 JSON으로만 답변

{{
  "scammer_message": "사기꾼의 첫 대사",
  "options": [
    {{ "id": 1, "text": "선택지1", "is_correct": false }},
    {{ "id": 2, "text": "선택지2", "is_correct": true  }},
    {{ "id": 3, "text": "선택지3", "is_correct": false }},
    {{ "id": 4, "text": "선택지4", "is_correct": false }}
  ]
}}
"""
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"},
            safety_settings=safety_settings,
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"🚨 start error: {e}")
        return {"error": str(e)}


# ── /api/chat ───────────────────────────────────────
@app.post("/api/chat")
async def continue_training(req: ChatRequest):
    try:
        sc_ctx   = SCENARIO_CONTEXT.get(req.scenario, SCENARIO_CONTEXT['prosecutor'])
        diff_ins = DIFFICULTY_INSTRUCTION.get(req.difficulty, DIFFICULTY_INSTRUCTION['medium'])
        is_last  = req.turn_count >= 10

        if is_last:
            prompt = f"""
보이스피싱 훈련이 종료되었어. 사용자의 마지막 대처: "{req.user_response}"
시나리오: {sc_ctx}

지금까지 훈련을 종합해 분석 리포트를 작성해. feedback은 2~3문장으로 구체적으로, tip은 실생활에 바로 쓸 수 있는 팁 1가지.

{{
  "scammer_message": "훈련이 종료되었습니다.",
  "is_finished": true,
  "report": {{
    "score": 0,
    "feedback": "총평 (2~3문장)",
    "tip": "핵심 예방 팁 1가지"
  }}
}}
"""
        else:
            prompt = f"""
너는 보이스피싱 사기꾼이야. 사용자가 "{req.user_response}"라고 반응했어.

[시나리오]
{sc_ctx}

[난이도 지침]
{diff_ins}

사용자 반응에 맞게 더 강하게 압박하는 다음 사기 대사와 새 선택지 4개를 만들어.
(정답 1~2개, 오답 2~3개 / 각 선택지는 30자 내외)
반드시 JSON으로만 답변.

{{
  "scammer_message": "다음 사기 대사",
  "is_finished": false,
  "options": [
    {{ "id": 1, "text": "선택지1", "is_correct": false }},
    {{ "id": 2, "text": "선택지2", "is_correct": true  }},
    {{ "id": 3, "text": "선택지3", "is_correct": false }},
    {{ "id": 4, "text": "선택지4", "is_correct": false }}
  ]
}}
"""
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"},
            safety_settings=safety_settings,
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"🚨 chat error: {e}")
        return {"error": str(e)}


# ── /api/analyze  (과학·통계 기반 분석 리포트) ────────
SCENARIO_NAME = {
    'prosecutor': '검사/수사기관 사칭',
    'bank':       '금융기관 사칭',
    'delivery':   '택배/관세청 사칭',
    'acquaintance':'지인/가족 사칭',
}

def _risk_level(pct: int) -> str:
    if pct < 20:  return '매우 낮음'
    if pct < 40:  return '낮음'
    if pct < 60:  return '보통'
    if pct < 80:  return '높음'
    return '매우 높음'

@app.post("/api/analyze")
async def analyze_training(req: AnalyzeRequest):
    """
    훈련 전체 기록(transcript)을 분석하여 과학·통계 기반 리포트를 생성한다.
    - 취약도 확률은 시뮬레이션 내 '실수율'로 결정론적으로 산출 (재현 가능)
    - 심리 조작 원리별 분석은 Cialdini 6원칙 + 피싱 취약성 연구(SCAM 모델)를 LLM에 적용
    """
    turns   = req.transcript
    total   = max(1, len(turns))
    correct = sum(1 for t in turns if t.is_correct)
    wrong   = total - correct
    score   = round(correct / total * 100)
    error_rate = wrong / total

    # 난이도 가중: 쉬운 난이도에서의 정답은 실전 방어력을 과대평가할 수 있어 보정
    diff_weight = {'easy': 1.15, 'medium': 1.0, 'hard': 0.9}.get(req.difficulty, 1.0)
    susceptibility = max(0, min(100, round(error_rate * 100 * diff_weight)))
    risk_level = _risk_level(susceptibility)

    sc_name = SCENARIO_NAME.get(req.scenario, req.scenario)
    sc_ctx  = SCENARIO_CONTEXT.get(req.scenario, '')

    # 대화 기록을 텍스트로 정리
    lines = []
    for t in turns:
        mark = '⭕정답' if t.is_correct else '❌오답'
        lines.append(
            f"[턴 {t.turn}] 사기수법: \"{t.scammer_message}\" / 사용자선택: \"{t.user_choice}\" "
            f"({mark}, 모범답안: \"{t.correct_answer}\")"
        )
    transcript_text = "\n".join(lines) if lines else "(기록 없음)"

    prompt = f"""
너는 보이스피싱 취약성을 평가하는 보안 행동심리 분석가야.
아래 사용자의 훈련 전체 기록을 학술적 프레임워크에 근거해 분석하고, 반드시 JSON으로만 답해.

[적용할 분석 프레임워크]
1) Cialdini의 설득 6원칙 (Influence, 2006): 권위(authority), 희소성·긴급성(scarcity), 사회적 증거(social_proof), 호감(liking), 상호성(reciprocity), 일관성·헌신(commitment)
2) 피싱 취약성 연구 — Suspicion-Cognition-Automaticity Model(SCAM; Vishwanath et al., 2011)과 의심·정보처리 깊이 관점

[시나리오] {sc_name} — {sc_ctx}
[난이도] {req.difficulty}

[훈련 기록]
{transcript_text}

[계산된 통계 (이 수치를 그대로 사용하고 해석만 추가)]
- 총 {total}턴 중 정답 {correct} / 오답 {wrong}
- 점수: {score}점
- 시뮬레이션 실수율 기반 추정 취약도: {susceptibility}% (위험등급: {risk_level})

[작성 규칙]
- 취약도 %는 '시뮬레이션 성과에 기반한 모델 추정치'임을 분명히 하고 단정적 의학·심리 진단처럼 쓰지 말 것
- principles에는 이 시나리오에서 사기꾼이 실제로 사용한 원리만 골라 평가 (사용 안 한 원리는 제외)
- vulnerability(0~100)는 해당 원리가 쓰인 턴에서 사용자가 얼마나 흔들렸는지로 추정
- 모든 텍스트는 한국어, 일반인이 이해할 쉬운 표현으로

다음 JSON 형식으로만 답변:
{{
  "headline": "이 사용자를 한 문장으로 규정 (예: '권위·긴급성 압박에 취약한 신중형 대응자')",
  "summary": "2~3문장 종합 평가. '이런 유형의 사용자는 실제 ○○ 상황에서 ~할 확률이 높다'는 통계적 해석 톤 포함",
  "user_type": "행동 유형 라벨 (예: 침착 방어형 / 권위 순응형 / 충동 반응형 등)",
  "principles": [
    {{ "key": "authority", "name": "권위", "vulnerability": 0, "comment": "이 원리에 대한 한 줄 진단" }}
  ],
  "strengths": ["잘한 점 1~3개"],
  "weaknesses": ["취약한 점 1~3개"],
  "statistical_insight": "통계·확률적 해석 2~3문장. 취약도 {susceptibility}%가 무슨 의미인지, 어떤 상황에서 위험이 커지는지를 프레임워크 근거로 설명",
  "recommendations": ["실생활 행동수칙 3개"],
  "tip": "가장 중요한 예방 팁 1가지",
  "methodology": "어떤 기법으로 분석했는지 1~2문장 설명",
  "references": ["Cialdini, R. (2006). Influence: The Psychology of Persuasion", "Vishwanath et al. (2011). SCAM 모델"]
}}
"""
    base = {
        "score": score,
        "total_turns": total,
        "correct": correct,
        "wrong": wrong,
        "susceptibility_percent": susceptibility,
        "risk_level": risk_level,
        "scenario_name": sc_name,
    }
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"},
            safety_settings=safety_settings,
        )
        llm = json.loads(response.text)
    except Exception as e:
        print(f"🚨 analyze error: {e}")
        # LLM 실패 시에도 통계 기반 최소 리포트는 제공
        llm = {
            "headline": f"{sc_name} 대응 결과",
            "summary": f"총 {total}턴 중 {correct}턴을 안전하게 대처했습니다. 추정 취약도는 {susceptibility}%입니다.",
            "user_type": "분석 제한",
            "principles": [],
            "strengths": [], "weaknesses": [],
            "statistical_insight": f"시뮬레이션 실수율({wrong}/{total})을 기반으로 한 추정 취약도는 {susceptibility}% 입니다.",
            "recommendations": ["기관·금융은 전화로 이체나 보안정보를 요구하지 않습니다.",
                                 "전화를 끊고 공식 대표번호로 직접 확인하세요.",
                                 "긴급·협박성 요구일수록 의심하세요."],
            "tip": "어떤 기관도 전화로 돈을 옮기라고 하지 않습니다.",
            "methodology": "시뮬레이션 내 실수율 기반 통계 추정 (LLM 상세분석 일시 불가)",
            "references": ["Cialdini, R. (2006). Influence", "Vishwanath et al. (2011). SCAM 모델"],
        }
    # 결정론적 통계가 항상 우선되도록 base를 마지막에 병합
    return {**llm, **base}
