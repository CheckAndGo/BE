from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

# -------------------------------------------------------------------
# 1. 스키마에서 사용할 Enum (선택 항목) 정의
# -------------------------------------------------------------------

class PriorityLevel(str, Enum):
    """항목의 중요도 (JSON 스키마 샘플 기반)"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class StatusLevel(str, Enum):
    """항목의 현재 상태 (JSON 스키마 샘플 기반)"""
    PENDING = "PENDING"
    DONE = "DONE"

# -------------------------------------------------------------------
# 2. RAG 지식 카드 모델 (초경량 RAG)
# -------------------------------------------------------------------

class RagCard(BaseModel):
    """
    Qdrant에 저장될 초경량 RAG 팩트 카드 (V1 아키텍처)
    (예: "knowledge/country/JP.yml"의 내용)
    """
    id: str = Field(..., description="팩트 고유 ID (예: 'jp_visa')")
    tags: List[str] = Field(..., description="검색용 키워드 (예: '일본', '비자', '서류')")
    fact: str = Field(..., description="LLM에게 제공될 핵심 팩트. (예: '일본 A형, 100V / 비자: 한국 여권 90일 무비자(관광)')")

# -------------------------------------------------------------------
# 3. FastAPI 입력 모델 (새로운 JSON 구조 반영)
# -------------------------------------------------------------------

class Budget(BaseModel):
    """여행 예산 모델 (새로운 JSON 구조 반영)"""
    rawInput: Optional[str] = Field(None, description="사용자가 입력한 예산 문자열 (예: '100만원')")

class Destination(BaseModel):
    """여행지 모델"""
    country: str
    city: str

class Period(BaseModel):
    """여행 기간 모델"""
    startDate: str = Field(..., description="YYYY-MM-DD")
    endDate: str = Field(..., description="YYYY-MM-DD")
    nights: int
    days: int

class Travelers(BaseModel):
    """여행자 모델"""
    count: int

# 기존 TripDetails를 대체하는 새로운 최상위 입력 모델
class ChecklistRequest(BaseModel):
    """
    FastAPI의 새로운 입력 모델. Flutter 앱에서 전송하는 전체 JSON 구조를 받습니다.
    """
    tripId: str
    locale: str
    destination: Destination
    period: Period
    travelers: Travelers
    budget: Optional[Budget] = None
    purpose: str = Field(..., description="여행 목적 (예: 휴양, 비즈니스)")
    lodging: Optional[Dict[str, str]] = None 
    transportation: Optional[Dict[str, str]] = None
    existingChecklist: Optional[Dict[str, Any]] = Field(None, description="기존 체크리스트 데이터 (요약 및 아이템)")

# -------------------------------------------------------------------
# 4. FastAPI 출력 모델 (LLM이 생성할 JSON 스키마)
# -------------------------------------------------------------------

class ChecklistItem(BaseModel):
    """체크리스트 개별 항목 (V1 스키마)"""
    id: str = Field(..., description="항목 고유 ID (예: 'doc-passport-validity')")
    title: str = Field(..., description="항목 제목 (한국어). 예: '여권 유효기간 확인'")
    due: str = Field(..., description="권장 마감일 (YYYY-MM-DD). startDate를 기준으로 LLM이 계산.")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM)
    requiresVerification: bool = Field(default=False, description="사용자/RAG가 팩트 확인이 필요한 경우 True")
    notes: Optional[str] = Field(None, description="추가 메모 (한국어). 예: '스캔본 클라우드 보관'")
    links: Optional[List[str]] = Field(None, description="참고 URL 목록")
    status: StatusLevel = Field(default=StatusLevel.PENDING)

class CategoryItems(BaseModel):
    """카테고리별 체크리스트 목록 (V1 스키마)"""
    category: str = Field(..., description="카테고리명 (예: '서류', '교통', '통신')")
    items: List[ChecklistItem]

class Progress(BaseModel):
    """진행률 요약 (V1 스키마)"""
    total: int
    done: int

class ChecklistResponse(BaseModel):
    """
    FastAPI의 최종 응답 모델.
    LLM이 생성해야 할 V1 JSON 스키마 전체 구조.
    """
    # 응답 모델의 tripMeta도 이제 ChecklistRequest의 핵심 정보만 담도록 간소화하거나, 
    # LLM이 생성한 Progress/Checklist와 함께 전송합니다. 
    # 여기서는 입력 모델인 ChecklistRequest의 핵심만 담도록 재정의합니다.
    tripMeta: ChecklistRequest 
    checklist: List[CategoryItems]
    progress: Progress