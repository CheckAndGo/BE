import json
from google.generativeai import types
from core.config import client, LLM_MODEL_NAME, SYSTEM_INSTRUCTION_PROMPT
from core.models import ChecklistResponse, ChecklistRequest, Progress 
from workers.retriever import retrieve_rag_content
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# -------------------------------------------------------------------
# 1. 인메모리 캐시 구현 (NFR: 비용/성능 목표 달성)
# -------------------------------------------------------------------
_CACHE: Dict[str, Any] = {}

# 입력 모델 ChecklistRequest 기반으로 캐시 키 생성
def generate_cache_key(request_data: ChecklistRequest) -> str:
    """
    여행의 핵심 요소를 기반으로 캐시 키를 생성합니다.
    (국가, 활동, 인원)이 동일하면 동일한 캐시를 사용합니다.
    """
    return f"llm_cache:{request_data.destination.country}-{request_data.purpose}-{request_data.travelers.count}"

def get_from_cache(key: str) -> Optional[ChecklistResponse]:
    """캐시에서 데이터를 조회합니다."""
    cached_data = _CACHE.get(key)
    if cached_data:
        print(f"캐시 적중! 캐시된 결과 반환: {key}")
        return ChecklistResponse.model_validate(cached_data)
    return None

def set_to_cache(key: str, value: ChecklistResponse):
    """캐시에 데이터를 저장합니다."""
    _CACHE[key] = value.model_dump()
    print(f"키에 대한 캐시 저장 완료: {key}")

# -------------------------------------------------------------------
# 2. LLM 호출 및 생성 로직 (RAG 통합)
# -------------------------------------------------------------------

# 입력 모델 ChecklistRequest를 기반으로 체크리스트 JSON 생성
def generate_checklist_json(request_data: ChecklistRequest) -> Optional[ChecklistResponse]:
    """
    ChecklistRequest 객체를 기반으로 RAG 검색 결과를 포함하여 LLM에게 최종 JSON을 요청합니다.
    """
    # 1. 캐시 확인 (NFR: 성능/비용)
    cache_key = generate_cache_key(request_data)
    cached_response = get_from_cache(cache_key)
    if cached_response:
        return cached_response
        
    if not client:
        print("오류: LLM 클라이언트가 초기화되지 않았습니다.")
        return None

    #  RAG 쿼리를 새로운 모델 구조에서 추출합니다.
    country = request_data.destination.country
    city = request_data.destination.city
    activity = request_data.purpose
    startDate = request_data.period.startDate
    duration = request_data.period.days
    people = request_data.travelers.count
    budget_raw = request_data.budget.rawInput if request_data.budget and request_data.budget.rawInput else 'N/A'
    
    # 2. RAG 검색 실행 (초경량 RAG)
    rag_query = f"{country} {city} {activity} 비자 전압 플러그"
    rag_cards = retrieve_rag_content(rag_query, country=country, top_k=1)
    
    # 3. 검색 결과를 프롬프트에 주입할 문맥으로 정리합니다.
    context_text = "\n\n--- CONTEXT FROM RAG KNOWLEDGE BASE ---\n"
    if rag_cards:
        card = rag_cards[0]
        context_text += f"Tags: {', '.join(card.tags)}. Fact: {card.fact}\n"
    else:
        context_text += "No specific RAG context found for this query. Use general knowledge only.\n"
    
    # 4. LLM에게 JSON 응답을 강제할 Pydantic 스키마를 가져오고 config를 설정합니다.
    json_schema = ChecklistResponse.model_json_schema()
    config_with_schema = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=json_schema             
    )
    
    # 5. 동적 프롬프트 조립 (RAG 문맥 포함)
    prompt = f"""
    {context_text}
    
    --- USER TRIP DETAILS ---
    - Country/City: {country} / {city}
    - Start Date: {startDate} (YYYY-MM-DD)
    - Duration: {duration} days
    - Purpose/Activity: {activity}
    - People: {people}
    - Budget (Raw Input): {budget_raw}
    
    Based on the trip details AND the RAG CONTEXT, generate the complete travel checklist following the strict JSON schema.
    Calculate 'due' dates relative to 'Start Date'.
    """
    
    # 6. LLM 호출
    try:
        print(f"LLM API 호출 중... (모델: {LLM_MODEL_NAME})")
        response = client.generate_content(
            contents=prompt,
            config=config_with_schema,
            system_instruction=SYSTEM_INSTRUCTION_PROMPT
        )
        
        # 7. 응답 파싱 및 검증
        json_string = response.text.strip()
        checklist_response = ChecklistResponse.model_validate_json(json_string)
        
        # 8. 성공 시 캐시에 저장
        set_to_cache(cache_key, checklist_response)
        
        return checklist_response
        
    except Exception as e:
        print(f"오류: LLM API 호출 또는 JSON 유효성 검사 중 오류 발생: {e}")
        return None