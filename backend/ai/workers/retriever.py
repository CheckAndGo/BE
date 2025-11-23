# workers/retriever.py

from typing import List
from qdrant_client.models import Filter, FieldCondition, MatchValue
from core.config import qdrant_client, QDRANT_COLLECTION, EMBEDDING_MODEL_NAME
from core.models import RagCard
import google.generativeai as genai
import os


# -------------------------------------------------------------------
# 1. 임베딩 클라이언트 설정
# -------------------------------------------------------------------
def get_embedding_client():
    """Gemini 임베딩용 클라이언트(genai 모듈) 반환"""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("[RAG] GEMINI_API_KEY 가 없습니다. 임베딩 불가.")
        return None

    # core.config 에서 이미 genai.configure(...) 해줬다고 가정
    return genai


def _ensure_model_name(model_name: str) -> str:
    """text-embedding-004 처럼 들어와도 models/ 접두사를 붙여준다."""
    if model_name.startswith("models/") or model_name.startswith("tunedModels/"):
        return model_name
    return f"models/{model_name}"


# -------------------------------------------------------------------
# 2. 벡터 검색 함수 (군집화 효과 적용)
# -------------------------------------------------------------------
def retrieve_rag_content(query_text: str, country: str, top_k: int = 1) -> List[RagCard]:
    """
    사용자 쿼리(여행 정보)를 기반으로 Qdrant에서 관련 RAG 팩트를 검색합니다.
    country 매개변수를 사용하여 특정 국가(군집) 내에서만 검색합니다.
    """
    # 0) Qdrant / 임베딩 클라이언트 확인
    if qdrant_client is None:
        print("[RAG] Qdrant 클라이언트가 초기화되지 않았습니다. RAG 건너뜀.")
        return []

    embedding_client = get_embedding_client()
    if embedding_client is None:
        print("[RAG] 임베딩 클라이언트가 없습니다. RAG 건너뜀.")
        return []

    # 1) 쿼리를 임베딩으로 변환
    model_name = _ensure_model_name(EMBEDDING_MODEL_NAME)

    try:
        embed_result = embedding_client.embed_content(
            model=model_name,
            content=query_text,
            task_type="RETRIEVAL_QUERY",
        )

        # google-generativeai 버전에 따라 dict 또는 객체로 올 수 있음
        if isinstance(embed_result, dict):
            query_vector = (
                embed_result.get("embedding")
                or (
                    embed_result.get("data", [{}])[0].get("embedding")
                    if isinstance(embed_result.get("data"), list)
                    else None
                )
            )
        else:
            # 객체 타입인 경우 .embedding 속성 시도
            query_vector = getattr(embed_result, "embedding", None)

        if not query_vector:
            print("[RAG] embed_content 에서 embedding 을 얻지 못했습니다. RAG 건너뜀.")
            return []

    except Exception as e:
        print(f"[Embedding] embed_content 호출 중 오류 발생: {e}")
        print("[RAG] 쿼리 임베딩 생성에 실패했습니다. RAG 건너뜀.")
        return []

    # 2) 국가 태그 필터 설정
    country_filter = Filter(
        must=[
            FieldCondition(
                key="tags",  # RagCard.tags 에 국가 태그가 들어있다고 가정
                match=MatchValue(value=country.lower()),
            )
        ]
    )

    # 3) Qdrant 검색 (버전별로 search 또는 query_points 둘 다 지원)
    try:
        if hasattr(qdrant_client, "search"):
            # 일부 버전에서 지원
            search_result = qdrant_client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_vector,
                query_filter=country_filter,
                limit=top_k,
                score_threshold=0.7,
            )
        elif hasattr(qdrant_client, "query_points"):
            # 최신 버전에서는 query_points 가 메인 API
            search_result = qdrant_client.query_points(
                collection_name=QDRANT_COLLECTION,
                query=query_vector,
                query_filter=country_filter,
                limit=top_k,
                score_threshold=0.7,
            )
        else:
            print(
                "[RAG] Qdrant 클라이언트에 search / query_points 둘 다 없습니다. "
                "qdrant-client 버전을 확인하세요."
            )
            return []

    except Exception as e:
        print(f"[RAG] Qdrant 검색 중 오류 발생: {e}")
        print("[RAG] 검색 실패, RAG 없이 진행합니다.")
        return []

    # 4) 결과를 RagCard 리스트로 변환
    rag_cards: List[RagCard] = []
    for hit in search_result:
        try:
            # hit 이 ScoredPoint 인 경우
            payload = None
            if hasattr(hit, "payload"):
                payload = hit.payload
            # hit 이 dict 형태인 경우
            elif isinstance(hit, dict) and "payload" in hit:
                payload = hit["payload"]
            # hit 이 (payload, score) 같은 tuple 인 경우
            elif isinstance(hit, tuple):
                # tuple 안에서 dict인 요소를 payload로 가정
                for elem in hit:
                    if isinstance(elem, dict):
                        payload = elem
                        break

            if not payload:
                continue

            card = RagCard.model_validate(payload)
            rag_cards.append(card)

        except Exception as e:
            print(f"[RAG] RAG 카드 페이로드 유효성 검사 중 오류 발생: {e}")

    print(f"[RAG] Qdrant에서 {len(rag_cards)}개 결과를 가져왔습니다.")
    return rag_cards
