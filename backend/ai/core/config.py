# core/config.py
import sys
import os
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai
from qdrant_client import QdrantClient

load_dotenv()

# ===================================================================
# 1. 환경 변수 로드
# ===================================================================
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash")

# 구글 Embedding 모델 (반드시 models/ 로 시작해야 함)
EMBEDDING_MODEL_NAME: str = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "models/text-embedding-004",
)

QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL")
QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "travel_tips")

# ===================================================================
# 2. 시스템 프롬프트 (system_instruction)
# ===================================================================
SYSTEM_INSTRUCTION_PROMPT = """
You are Check&Go, an expert AI Travel Checklist Generator.
Your entire response must be a single, valid JSON object. Do not include markdown or explanations.
You must strictly adhere to a JSON structure that represents a travel checklist.

--- RULES ---
1.  **Language**: All 'title' and 'notes' fields must be in **Korean**.
2.  **Categories**: Use categories like ["서류","교통","숙박","보험","금융","통신","준비물"] as needed.
3.  **Due Dates**: Calculate 'due' dates (YYYY-MM-DD) based on the trip 'startDate'. Critical items (like passports) should be due 1-2 weeks before.
4.  **IDs**: Generate a unique kebab-case ID for each item (e.g., 'doc-passport-check').
5.  **Verification**: If a fact is uncertain or based on RAG context (like visa rules, plug types), set 'requiresVerification' to **true** and add context in 'notes'.
6.  **RAG Context**: Use the provided 'RAG CONTEXT' to verify facts (e.g., visa rules, power plug types). If context is available, use it to set 'notes' and 'requiresVerification'.
"""

# ===================================================================
# 3. Gemini LLM 클라이언트 초기화
# ===================================================================
client = None
if not GEMINI_API_KEY:
    print("경고: GEMINI_API_KEY를 찾을 수 없습니다. LLM 기능이 비활성화됩니다.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # 👉 system_instruction 은 여기서 설정하고,
        # generate_content() 에서는 더 이상 system_instruction 인자를 넘기지 않는다.
        client = genai.GenerativeModel(
            model_name=LLM_MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION_PROMPT,
        )
        print(f"Gemini 클라이언트 초기화 성공 (모델: {LLM_MODEL_NAME})")
    except Exception as e:
        print(f"오류: Gemini 클라이언트 초기화 중 오류 발생: {e}")
        client = None

# ===================================================================
# 4. Qdrant 벡터 데이터베이스 클라이언트 초기화 (RAG)
# ===================================================================
qdrant_client = None
if QDRANT_URL and QDRANT_API_KEY:
    try:
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )
        print("Qdrant 클라이언트 초기화 성공.")
    except Exception as e:
        print(f"오류: Qdrant 클라이언트 초기화 중 오류 발생: {e}")
        qdrant_client = None
else:
    print("경고: QDRANT_URL 또는 QDRANT_API_KEY가 없습니다. RAG가 비활성화됩니다.")
