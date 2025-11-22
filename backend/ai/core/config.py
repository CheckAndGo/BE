import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai import types
from qdrant_client import QdrantClient # Qdrant 클라이언트를 위한 임포트
from typing import Optional

# 환경 변수 로드 (프로젝트 루트의 .env 파일)
load_dotenv()

# ===================================================================
# 1. 환경 변수 로드
# ===================================================================
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash")
EMBEDDING_MODEL_NAME: str = "text-embedding-004" 

QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL")
QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "travel_tips")

# ===================================================================
# 2. Gemini AI 설정 및 클라이언트 초기화 (LLM)
# ===================================================================
client = None
if not GEMINI_API_KEY:
    print("경고: GEMINI_API_KEY를 찾을 수 없습니다. LLM 기능이 비활성화됩니다.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        client = genai.GenerativeModel(model_name=LLM_MODEL_NAME)
    except Exception as e:
        print(f"오류: Gemini 클라이언트 초기화 중 오류 발생: {e}")

# ===================================================================
# 3. V1 아키텍처를 위한 시스템 프롬프트 (핵심 규칙)
# ===================================================================
SYSTEM_INSTRUCTION_PROMPT = """
You are Check&Go, an expert AI Travel Checklist Generator.
Your entire response must be a single, valid JSON object. Do not include markdown or explanations.
You must strictly adhere to the provided JSON schema.

--- RULES ---
1.  **JSON Schema**: Strictly follow the Pydantic JSON schema provided.
2.  **Language**: All 'title' and 'notes' fields must be in **Korean**.
3.  **Categories**: Use categories like ["서류","교통","숙박","보험","금융","통신","준비물"] as needed.
4.  **Due Dates**: Calculate 'due' dates (YYYY-MM-DD) based on the trip 'startDate'. Critical items (like passports) should be due 1-2 weeks before.
5.  **IDs**: Generate a unique kebab-case ID for each item (e.g., 'doc-passport-check').
6.  **Verification**: If a fact is uncertain or based on RAG context (like visa rules, plug types), set 'requiresVerification' to **true** and add context in 'notes'.
7.  **RAG Context**: Use the provided 'RAG CONTEXT' to verify facts (e.g., visa rules, power plug types). If context is available, use it to set 'notes' and 'requiresVerification'.
"""

# ===================================================================
# 4. Qdrant 벡터 데이터베이스 설정 및 클라이언트 초기화 (RAG)
# ===================================================================
qdrant_client = None
if QDRANT_URL and QDRANT_API_KEY:
    try:
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )
        print("Qdrant 클라이언트 초기화 성공.")
    except Exception as e:
        print(f"오류: Qdrant 클라이언트 초기화 중 오류 발생: {e}")
        qdrant_client = None
else:
    print("경고: QDRANT URL 또는 API KEY를 찾을 수 없습니다. Qdrant 클라이언트가 초기화되지 않았습니다.")