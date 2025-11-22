LLM + RAG 동작 개념
단계	구성요소	역할
①	Frontend(Firebase)	사용자가 여행 정보를 입력
②	Firebase Function	Python FastAPI로 POST 요청 전송
③	Python API (LLM 서버)	Firestore/Qdrant에서 문맥 검색 후 LLM 호출
④	LLM (Gemini/Claude)	"국가·날씨·활동 기반 체크리스트" 생성
⑤	Firebase에 저장	생성된 리스트를 클라이언트로 반환 및 캐시
---
```
CheckAndGo/
 ┣ backend/
 ┃ ┣ functions/                # 기존 Firebase Functions (TypeScript)
 ┃ ┗ ai/                       # 🧠 새로 추가되는 Python LLM 서버
 ┃    ┣ .env                   # API 키, Qdrant 설정 등
 ┃    ┣ requirements.txt       # pip 패키지 목록
 ┃    ┣ app.py                 # FastAPI 메인 서버 (엔드포인트 정의)
 ┃    ┣ core/                  # 환경설정/로깅 등 핵심 유틸
 ┃    │  ┣ config.py
 ┃    │  ┗ logger.py
 ┃    ┣ workers/               # LLM + RAG 관련 모듈
 ┃    │  ┣ embedder.py        # 임베딩 생성 (KURE-v1 등)
 ┃    │  ┣ retriever.py       # Qdrant / Firestore 검색
 ┃    │  ┣ generator.py       # LLM 호출 (Gemini/Claude/OpenAI)
 ┃    │  ┗ pipeline.py        # RAG 파이프라인 (검색→생성)
 ┃    ┗ tests/                 # 간단한 API 테스트 코드
 ┃       ┗ test_recommend.py
 ┣ firebase.json
 ┣ firestore.rules
 ┗ README.md
```