from typing import List
from qdrant_client import models
# Filter, FieldCondition, MatchValue 임포트 (군집화/필터링용)
from qdrant_client.models import Filter, FieldCondition, MatchValue
from core.config import qdrant_client, QDRANT_COLLECTION, EMBEDDING_MODEL_NAME
from core.models import RagCard # V1 스키마의 RagCard 모델 사용
import google.generativeai as genai
import os

# -------------------------------------------------------------------
# 1. 임베딩 클라이언트 설정
# -------------------------------------------------------------------
def get_embedding_client():
    # retriever.py에서는 Client() 대신 genai 모듈 자체를 반환하도록 함.
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        return None
    
    # config.py에서 이미 configure 했으므로, genai 모듈을 반환합니다.
    return genai 

# -------------------------------------------------------------------
# 2. 벡터 검색 함수 (군집화 효과 적용)
# -------------------------------------------------------------------
# country 매개변수를 추가로 받습니다.
def retrieve_rag_content(query_text: str, country: str, top_k: int = 1) -> List[RagCard]:
    """
    사용자 쿼리(여행 정보)를 기반으로 Qdrant에서 관련 RAG 팩트를 검색합니다.
    country 매개변수를 사용하여 특정 국가(군집) 내에서만 검색합니다.
    """
    if not qdrant_client:
        print("Retrieval Warning: 임베딩 클라이언트가 초기화되지 않았습니다.")
        return []

    embedding_client = get_embedding_client()
    if not embedding_client:
        print("Retrieval Warning: 임베딩 클라이언트가 초기화되지 않았습니다.")
        return []

    # 1. 사용자 쿼리를 임베딩합니다.
    query_vector = embedding_client.models.embed_content(
        model=EMBEDDING_MODEL_NAME,
        content=query_text,
        task_type="RETRIEVAL_QUERY"
    )['embedding']

    # 군집화 효과를 위한 메타데이터 필터링 조건 생성 (국가 태그 필터링)
    country_filter = Filter(
        must=[
            FieldCondition(
                key="tags",  # RagCard의 tags 필드
                # 국가 이름을 소문자로 변환하여 tags 리스트에 일치하는지 확인 (대소문자 무시)
                match=MatchValue(value=country.lower()) 
            )
        ]
    )

    # 2. Qdrant에서 검색을 수행합니다.
    search_result = qdrant_client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_vector,
        # 필터 적용: 해당 국가 태그가 있는 벡터(군집) 내에서만 검색합니다.
        query_filter=country_filter, 
        limit=top_k,
        score_threshold=0.7 
    )
    
    # 3. 결과를 RagCard 객체 리스트로 변환합니다.
    rag_cards: List[RagCard] = []
    for hit in search_result:
        try:
            card = RagCard.model_validate(hit.payload)
            rag_cards.append(card)
        except Exception as e:
            print(f"오류: RAG 카드 페이로드 유효성 검사 중 오류 발생: {e}")

    return rag_cards