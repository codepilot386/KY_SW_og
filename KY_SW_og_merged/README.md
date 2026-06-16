# KY_SW_og 통합본

보이스피싱 예방 훈련용 웹앱입니다.

## 1. 백엔드 실행

```powershell
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
```

`.env` 파일을 열고 `GEMINI_API_KEY`를 본인 키로 바꾼 뒤 실행합니다.

```powershell
python main.py
```

백엔드 주소: `http://127.0.0.1:8000`

## 2. 프론트엔드 실행

새 터미널에서:

```powershell
cd frontend
npm install
npm run dev
```

브라우저에 표시되는 Vite 주소로 접속하세요. 보통 `http://127.0.0.1:5173` 입니다.

## 3. 구성

- `backend/main.py`: FastAPI + Gemini API
- `frontend/src/App.jsx`: React UI + API 연결 + 브라우저 기본 TTS
- `frontend/src/App.css`: 앱 스타일
- `frontend/src/index.css`: 전역 스타일
