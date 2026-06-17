import google.generativeai as genai
import os
from dotenv import load_dotenv

# 환경 변수 불러오기
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("👇 내 API 키로 사용할 수 있는 모델 목록 👇")
for m in genai.list_models():
    # 텍스트 생성이 가능한 모델만 걸러서 출력
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)