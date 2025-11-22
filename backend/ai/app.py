from fastapi import FastAPI, HTTPException, Depends, Security, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.models import ChecklistRequest, ChecklistResponse 
from workers.generator import generate_checklist_json
from typing import Optional

# -------------------------------------------------------------------
# 1. FastAPI 애플리케이션 초기화 및 라우터 정의
# -------------------------------------------------------------------
app = FastAPI(
    title="Check&Go AI Backend (v1)",
    description="LLM을 이용해 캘린더 일정 기반 체크리스트를 추천합니다."
)

# [명세서 규약 준수] Base URL /api/v1 적용을 위한 라우터
api_router = APIRouter(prefix="/api/v1")

@app.get("/")
def read_root():
    """서버 상태 확인용 엔드포인트."""
    return {"status": "ok", "service": "Check&Go LLM Boost API"}

# -------------------------------------------------------------------
# 2. 보안 설정 및 인증 의존성 정의 (규약 준수: Bearer Token)
# -------------------------------------------------------------------

# HTTP Bearer Scheme 정의 (Authorization: Bearer <token> 을 요구)
security_scheme = HTTPBearer(auto_error=False) 

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)):
    """
    [규약 준수] JWT Bearer Token 유효성 검사 함수.
    """
    if credentials is None or not credentials.credentials:
        # [규약 준수] 401 Unauthorized Response Code 반환
        raise HTTPException(
            status_code=401, 
            detail="Unauthorized", 
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 토큰이 존재하면 통과 처리
    return credentials.credentials 

# -------------------------------------------------------------------
# 3. 핵심 기능 엔드포인트 구현: POST /api/v1/llm/boost
# -------------------------------------------------------------------

# [규약 준수] 엔드포인트가 api_router를 사용합니다.
@api_router.post("/llm/boost", response_model=ChecklistResponse)
async def llm_boost_recommendation(
    # ChecklistRequest 모델을 입력으로 받습니다.
    request_data: ChecklistRequest, 
    # [규약 준수] 인증 의존성 추가: 토큰이 있어야만 접근 가능합니다.
    token: str = Depends(verify_token) 
):
    """
    [AI 보강 추천] Flutter 앱으로부터 여행 일정 정보를 받아 AI 보강 체크리스트를 요청합니다.
    FastAPI가 토큰 검증, 입력 데이터 유효성 검증(422)을 모두 처리합니다.
    """
    # 로깅 메시지를 새로운 데이터 구조에 맞춥니다.
    print(f"\n[요청] 인증 성공. 여행 처리 중: {request_data.destination.country} ({request_data.purpose})") 
    
    # generator.py의 함수를 호출하여 LLM에게 요청합니다.
    checklist = generate_checklist_json(request_data)
    
    if checklist is None:
        # [규약 준수] LLM 처리 실패 시 500 Response Code 반환
        raise HTTPException(status_code=500, detail="AI 체크리스트 생성에 실패했습니다. (LLM 처리 오류 또는 시간 초과)")
    
    print(f"[응답] {len(checklist.checklist)}개 카테고리로 체크리스트 생성 성공.")
    
    # [규약 준수] 200 Response Code와 Pydantic 모델(JSON) 반환
    return checklist

# -------------------------------------------------------------------
# 4. 라우터 마운트
# -------------------------------------------------------------------
# 명세서의 /api/v1 경로를 따르도록 라우터를 메인 앱에 포함합니다.
app.include_router(api_router)