# AI 보이스피싱 대응 및 훈련 플랫폼

## 프로젝트 소개

**AI 보이스피싱 대응 및 훈련 플랫폼**은 사용자가 실제 보이스피싱 상황과 유사한 시나리오를 체험하며 안전한 대응 방법을 학습할 수 있도록 제작한 웹 기반 훈련 시스템입니다.

본 프로젝트는 보이스피싱 유형별 상황을 제시하고, 사용자의 선택에 따라 점수를 계산하며, 훈련 종료 후 잘한 점과 주의해야 할 점을 분석하여 제공하는 것을 목표로 합니다.

---

## 주요 기능

### 사용자 기능

- 회원가입 및 로그인
- 훈련 유형 선택
  - 기관 사칭
  - 지인 사칭
  - 대출 사기형
- 보이스피싱 시나리오 기반 선택형 훈련
- 선택 결과에 따른 점수 계산
- 훈련 종료 후 결과 분석 제공
- 과거 훈련 점수 확인
- TTS 음성 안내 기능

### 관리자 기능

- 관리자 계정 로그인
- 회원 목록 조회
- 회원 아이디 수정
- 회원 비밀번호 재설정
- 회원 삭제
- 훈련 기록 조회
- 훈련 기록 삭제

---

## 사용 기술

### 개발 환경

- Visual Studio Code
- Git / GitHub
- Render

### 프론트엔드

- React
- Vite
- JavaScript / JSX
- CSS
- Axios

### 백엔드

- Python
- FastAPI
- Uvicorn
- Pydantic

### 데이터베이스

- SQLite

### 외부 API

- Gemini API
- Typecast API

---

## 시스템 구조

```text
사용자 웹 브라우저
        ↓
React 기반 프론트엔드
        ↓
FastAPI 백엔드 API 서버
        ↓
SQLite 데이터베이스
        ↓
Gemini API / Typecast API
```

---

## 폴더 구조

```text
KY_SW_og_merged/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── app.db
│   └── static/
│       ├── index.html
│       └── assets/
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── src/
    │   ├── App.jsx
    │   └── App.css
    └── dist/
```

---

## 실행 방식

### 개발자 실행 방식

개발자는 Visual Studio Code 환경에서 프로젝트를 개발합니다. 백엔드는 Python FastAPI 기반으로 작성되었으며, 로컬 개발 환경에서는 Uvicorn 서버를 이용해 실행합니다. 프론트엔드는 React와 Vite를 이용해 개발하며, 개발 단계에서는 Vite 개발 서버로 테스트하거나 빌드 후 FastAPI 서버에 정적 파일 형태로 포함하여 실행합니다.

개발 흐름은 다음과 같습니다.

```text
1. Visual Studio Code에서 소스 코드 수정
2. FastAPI 서버를 로컬에서 실행
3. React 프론트엔드 수정 및 빌드
4. 빌드된 정적 파일을 backend/static 폴더에 복사
5. GitHub에 코드 업로드
6. Render를 통해 배포 및 실행
```

### 일반 사용자 실행 방식

일반 사용자는 별도의 프로그램 설치 없이 웹 브라우저를 통해 배포된 서비스 주소에 접속하여 시스템을 이용합니다. 사용자가 웹 페이지에 접속하면 FastAPI 서버가 React로 제작된 화면을 제공하고, 로그인, 회원가입, 훈련 진행, 결과 확인 등의 기능은 HTTP 기반 API 요청을 통해 처리됩니다.

사용자 이용 흐름은 다음과 같습니다.

```text
1. 사용자가 웹 브라우저로 서비스 주소에 접속
2. 로그인 또는 회원가입 진행
3. 훈련 유형 선택
4. 보이스피싱 상황에 대한 대응 선택
5. 서버에서 점수 계산 및 결과 분석 처리
6. 결과 화면에서 점수, 피드백, 주의사항 확인
```

---

## 로컬 실행 방법

### 1. 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
python main.py
```

또는 Uvicorn으로 직접 실행할 수 있습니다.

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

로컬 개발 시 기본 접속 주소는 다음과 같습니다.

```text
http://localhost:5173
```

백엔드 API 서버 주소는 다음과 같습니다.

```text
http://127.0.0.1:8000
```

---

## 배포 방식

본 프로젝트는 React 프론트엔드를 빌드한 뒤, 빌드 결과물을 FastAPI 백엔드의 `static` 폴더에 포함하여 Render에 단일 서버 형태로 배포합니다.

배포 구조는 다음과 같습니다.

```text
Render 서버
├── FastAPI API 제공
└── React 정적 파일 제공
```

Render 실행 명령 예시는 다음과 같습니다.

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 프론트엔드 빌드 및 백엔드 포함 방법

프론트엔드를 수정한 뒤에는 반드시 다시 빌드하고, 빌드 결과를 백엔드의 `static` 폴더에 복사해야 합니다.

```powershell
cd frontend
npm.cmd run build

Remove-Item -Recurse -Force ..\backend\static -ErrorAction SilentlyContinue
Copy-Item -Recurse .\dist ..\backend\static
```

그 후 GitHub에 변경사항을 업로드합니다.

```bash
git add .
git commit -m "update project"
git push
```

---

## 환경 변수

백엔드 실행을 위해 다음 환경 변수가 필요합니다.

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
TYPECAST_API_KEY=your_typecast_api_key
TYPECAST_VOICE_ID=your_typecast_voice_id
```

주의사항:

- `.env` 파일은 GitHub에 업로드하지 않습니다.
- API 키는 Render의 Environment Variables에 등록하여 사용합니다.
- `TYPECAST_VOICE_ID`는 Typecast에서 제공하는 유효한 voice_id 값을 사용해야 합니다.

---

## 데이터베이스 구조

본 프로젝트는 SQLite를 사용하며, 주요 테이블은 다음과 같습니다.

### users

사용자 계정 정보를 저장합니다.

```text
id
username
password_hash
created_at
```

### sessions

로그인 세션 토큰을 저장합니다.

```text
token
user_id
created_at
```

### training_scores

사용자의 훈련 점수를 저장합니다.

```text
id
user_id
scenario_type
score
result_label
created_at
```

---

## 보안 처리

사용자 비밀번호는 원문으로 저장하지 않고 해시값으로 저장합니다. 비밀번호는 SHA-256 처리 후 bcrypt를 이용해 해시화하여 저장하며, 로그인 시 입력된 비밀번호를 같은 방식으로 처리한 뒤 저장된 해시값과 비교합니다.

따라서 관리자도 사용자의 실제 비밀번호를 확인할 수 없으며, 필요한 경우 새 비밀번호로 재설정하는 방식으로 처리합니다.

---

## 훈련 결과 분석 기능

훈련이 종료되면 사용자의 점수와 선택 기록을 기반으로 결과 분석을 제공합니다.

분석 항목은 다음과 같습니다.

- 최종 점수
- 안전 / 주의 / 위험 판정
- 잘한 점
- 조심해야 할 점
- 틀린 선택에 대한 핵심 피드백
- 다음 훈련을 위한 팁

---

## 관리자 계정

관리자 기능은 아이디가 `admin`인 계정으로 로그인했을 때 사용할 수 있습니다.

관리자 기능:

```text
회원 목록 조회
회원 정보 수정
비밀번호 재설정
회원 삭제
훈련 기록 조회
훈련 기록 삭제
```

---

## 프로젝트 특징

- 실제 보이스피싱 상황과 유사한 훈련 시나리오 제공
- 사용자의 선택에 따른 점수 계산
- 훈련 종료 후 맞춤형 결과 분석 제공
- 관리자모드를 통한 사용자 및 기록 관리
- 웹 브라우저 기반 서비스로 별도 설치 없이 사용 가능
- FastAPI와 React를 하나의 Render 서버에서 통합 제공

---

## 향후 개선 방향

- PostgreSQL 등 외부 데이터베이스 연동
- 사용자별 상세 통계 시각화
- 훈련 난이도 조절 기능 추가
- 더 다양한 보이스피싱 유형 추가
- 모바일 화면 최적화 강화
- Typecast 음성 종류 선택 기능 추가

---

## 라이선스

본 프로젝트는 교육 및 학습 목적의 프로젝트입니다.
