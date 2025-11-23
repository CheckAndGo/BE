# ai/tools/init_qdrant_indexes.py
import os
import sys

# 프로젝트 루트(= ai 디렉터리) 기준으로 상위 경로를 sys.path에 추가
# 예: /Users/.../CheckAndGo/backend/ai
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from qdrant_client import models
from core.config import qdrant_client, QDRANT_COLLECTION


def main():
    if qdrant_client is None:
        print("❌ Qdrant 클라이언트가 초기화되지 않았습니다. .env 설정 확인 필요.")
        return

    print(f"ℹ️ 컬렉션: {QDRANT_COLLECTION} 에 'tags' 인덱스 생성 시도 중...")

    # 이미 인덱스가 있을 수도 있으니 예외는 한 번 잡아준다
    try:
        qdrant_client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="tags",
            field_schema=models.KeywordIndexParams(
                type="keyword",
            ),
        )
        print("✅ 'tags' 필드에 keyword 인덱스 생성 완료!")
    except Exception as e:
        print(f"⚠️ 인덱스 생성 중 오류(이미 있을 수도 있음): {e}")


if __name__ == "__main__":
    main()
