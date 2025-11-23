import json
import re
from google.generativeai import types
from core.config import client, LLM_MODEL_NAME, SYSTEM_INSTRUCTION_PROMPT
from core.models import ChecklistResponse, ChecklistRequest, Progress
from workers.retriever import retrieve_rag_content
from typing import Optional, Dict, Any, List
from datetime import datetime

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
# 2. LLM JSON → ChecklistResponse 로 변환하는 헬퍼
# -------------------------------------------------------------------

def _normalize_item_dict(raw: Dict[str, Any], request_data: ChecklistRequest) -> Dict[str, Any]:
    """
    LLM이 준 개별 아이템 dict를 ChecklistItem 스키마에 맞는 dict로 정규화.
    (Pydantic이 dict → ChecklistItem으로 변환해 준다)
    """
    title = (raw.get("title") or "").strip()
    if not title:
        title = "준비물"

    # id 없으면 title 기반으로 생성
    _id = raw.get("id")
    if not _id:
        safe = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "item"
        _id = f"item-{safe}"

    # due 없으면 startDate 기준으로 기본값
    due = raw.get("due")
    if not due:
        try:
            start = datetime.fromisoformat(request_data.period.startDate).date()
            due = start.isoformat()
        except Exception:
            due = datetime.utcnow().date().isoformat()

    priority = raw.get("priority", "MEDIUM")
    status = raw.get("status", "PENDING")
    requires_verification = bool(raw.get("requiresVerification", False))
    notes = raw.get("notes")
    links = raw.get("links") if isinstance(raw.get("links"), list) else None

    return {
        "id": _id,
        "title": title,
        "due": due,
        "priority": priority,
        "requiresVerification": requires_verification,
        "notes": notes,
        "links": links,
        "status": status,
    }

def _build_checklist_response_from_raw(
    raw: Dict[str, Any],
    request_data: ChecklistRequest,
) -> ChecklistResponse:
    """
    LLM이 준 raw JSON(dict)을 ChecklistResponse 스키마로 변환.
    - tripMeta: 입력으로 받은 request_data 그대로 사용
    - checklist: 
        - 이미 category / items 구조면 그대로 쓰고
        - 아니면 전부 '기본' 카테고리 하나로 묶는다
    - progress: total / done 단순 계산 (현재 done=0 으로 시작)
    """
    categories: List[Dict[str, Any]] = []

    if not isinstance(raw, dict):
        raise ValueError("LLM JSON이 dict 형태가 아닙니다.")

    # 1) 우선 raw["checklist"] 를 본다
    cl = raw.get("checklist")
    if isinstance(cl, list) and len(cl) > 0:
        first = cl[0]
        # 이미 {"category": "...", "items": [...]} 구조인 경우
        if isinstance(first, dict) and "items" in first:
            for block in cl:
                if not isinstance(block, dict):
                    continue
                cat_name = block.get("category") or "기본"
                raw_items = block.get("items") or []
                norm_items = [
                    _normalize_item_dict(it, request_data)
                    for it in raw_items
                    if isinstance(it, dict)
                ]
                if norm_items:
                    categories.append({
                        "category": cat_name,
                        "items": norm_items,
                    })
        else:
            # checklist 자체가 item 리스트인 경우 → '기본' 카테고리 하나로 묶기
            norm_items = [
                _normalize_item_dict(it, request_data)
                for it in cl
                if isinstance(it, dict)
            ]
            if norm_items:
                categories.append({
                    "category": "기본",
                    "items": norm_items,
                })

    # 2) checklist가 없고 items 만 있는 경우
    if not categories and isinstance(raw.get("items"), list):
        norm_items = [
            _normalize_item_dict(it, request_data)
            for it in raw["items"]
            if isinstance(it, dict)
        ]
        if norm_items:
            categories.append({
                "category": "기본",
                "items": norm_items,
            })

    if not categories:
        raise ValueError("LLM JSON에서 checklist/items 를 찾을 수 없습니다.")

    total = sum(len(cat["items"]) for cat in categories)
    done = 0  # 초기에는 완료 0 개로 가정

    progress = Progress(total=total, done=done)

    # ChecklistResponse 생성 시 Pydantic이 dict → CategoryItems / ChecklistItem 으로 변환
    return ChecklistResponse(
        tripMeta=request_data,
        checklist=categories,
        progress=progress,
    )

# -------------------------------------------------------------------
# 3. LLM 호출 및 생성 로직 (RAG 통합)
# -------------------------------------------------------------------

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
    budget_raw = (
        request_data.budget.rawInput
        if request_data.budget and request_data.budget.rawInput
        else "N/A"
    )

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

    # 4. LLM에게 JSON 응답을 요청하는 GenerationConfig
    #    → Pydantic schema는 여기서 강제하지 않고, 단순히 JSON만 요구
    config_with_schema = types.GenerationConfig(
        response_mime_type="application/json",
        # 필요하면 temperature, max_output_tokens 등 추가 가능
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

    Based on the trip details AND the RAG CONTEXT, generate the complete travel checklist.
    The response MUST be a single JSON object.
    """

    # 6. LLM 호출 + JSON 파싱 + ChecklistResponse 변환
    try:
        print(f"LLM API 호출 중... (모델: {LLM_MODEL_NAME})")
        response = client.generate_content(
            contents=prompt,
            generation_config=config_with_schema,
            # system_instruction는 이 버전에서 지원 안 해서 제거
        )
        raw_text = response.text.strip()
        try:
            raw_json = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"오류: LLM 응답이 JSON 형식이 아닙니다: {e}")
            print("LLM raw response:", raw_text[:500])
            return None

        try:
            checklist_response = _build_checklist_response_from_raw(
                raw_json, request_data
            )
        except Exception as e:
            print(f"오류: LLM JSON을 ChecklistResponse로 변환하는 중 오류 발생: {e}")
            print("LLM parsed JSON (앞부분):", str(raw_json)[:500])
            return None

        # 캐시에 저장
        set_to_cache(cache_key, checklist_response)
        return checklist_response

    except Exception as e:
        print(f"오류: LLM API 호출 중 오류 발생: {e}")
        return None
