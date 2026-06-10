# KY_SW_og

# 팀원 역할 분담
PM 김우진 : 프로젝트 총괄 및 일정 관리 , 요구사항 기획  
CM 김현준 : 버전 및 산출물 관리  
QA 김태연 : 기능 및 오류 테스트, 피드백 및 최종 점검  
ENG1 박현민 : 제품의 기능 구현 및 코드 개발  
ENG2 곽준성 : 제품의 기능 구현 및 코드 개발  
ENG3 박수린 : 제품의 기능 구현 및 코드 개발


# 프로젝트 주제
보이스피싱 대응 및 훈련 사이트

# 프로젝트 개요
VoiceMate는 급증하는 보이스피싱 범죄로부터 고령층 및 사회적 약자를 보호하기 위해, 실제와 유사한 피싱 상황을 가상으로 체험하고 대응 능력을 키우는 교육 시뮬레이션 플랫폼입니다. 

# 주요 기능
## 1.AI를 통한 보이스피싱 이지선다 문제 생성
## 2.실제 보이스피싱의 압박감을 느끼기 위한 타임어택 시스템
## 3.훈련종료후 결과 리포트와 취약점 분석
## 4.실시간 오답 피드백


<img width="1408" height="768" alt="Image" src="https://github.com/user-attachments/assets/ca3ead49-0090-4f4f-bd97-64be21aede48" />

# 기술스택
Backend : FastAPI(비동기 처리를 통한 고성능 API 서버 구축)  
Frontend : React(사용자 인터페이스(UI) 및 정적 파일 빌드/서빙)  
Database : SQLite3(회원정보,세션 토큰, 훈련 점수 경량 관리)  
AI  /  LLM : Google-Gemini(gemini를 통한 실시간 시나리오 생성)  
Audio  /  TTS : Typecast SDK(ssfm-v30 모델 기반 감정 반영 음성 합성)  
Security : Passlib(SHA-256 전처리 및 Bcrypt 단방향 비밀번호 암호화)
  


# 실행화면
<img width="50%" height="909" alt="Image" src="https://github.com/user-attachments/assets/c640de3b-613d-48b5-a03c-d2b8a9bfb86f" />
<img width="50%" height="910" alt="Image" src="https://github.com/user-attachments/assets/c4b1a984-388d-4822-9f5d-7e55a24b8928" />

<img width="50%" height="910" alt="Image" src="https://github.com/user-attachments/assets/2fe96d8a-d34a-4e98-b3b6-46cdcd188f45" />


