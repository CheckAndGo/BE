import sys
import os
# 모듈 경로 설정을 위해 이 코드는 유지
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from typing import List
from qdrant_client import models
from core.config import qdrant_client, QDRANT_COLLECTION, EMBEDDING_MODEL_NAME
from core.models import RagCard
from qdrant_client.http.exceptions import UnexpectedResponse

# 1. 임베딩 클라이언트 설정
def get_embedding_client():
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("오류: GEMINI_API_KEY를 찾을 수 없습니다. 임베딩이 불가능합니다.")
        return None
    
    
    import google.generativeai as genai
    genai.configure(api_key=gemini_api_key)

    return genai

# 2. V1 아키텍처 RAG 데이터 샘플
RAG_DATA_SAMPLES: List[RagCard] = [
    # =========================================================
    # 1. 필수 서류 및 규정 (비자/입국) [총 8개]
    # =========================================================
    RagCard(
        id="visa_us_canada",
        tags=["미국", "캐나다", "비자", "ESTA", "eTA", "서류"],
        fact="미국: ESTA(전자여행허가) 필수. / 캐나다: eTA(전자여행허가) 필수. 두 국가 모두 최소 72시간 전에 신청해야 합니다."
    ),
    RagCard(
        id="visa_eu_schengen",
        tags=["프랑스", "스페인", "이탈리아", "독일", "네덜란드", "유럽", "솅겐", "비자"],
        fact="솅겐 국가(유럽): 180일 중 90일 무비자 체류 가능. 입국 시 왕복 항공권 및 숙소 바우처를 요구할 수 있습니다."
    ),
    RagCard(
        id="visa_oceania",
        tags=["호주", "뉴질랜드", "비자", "서류"],
        fact="호주: ETA(전자여행허가) 필요. / 뉴질랜드: NZeTA(전자여행허가) 필요. 여행 전 온라인 신청 필수입니다."
    ),
    RagCard(
        id="visa_latam_brazil",
        tags=["브라질", "남미", "비자", "서류"],
        fact="브라질 여행: 한국 여권 소지자는 관광 목적으로 최대 90일 무비자 체류 가능합니다."
    ),
    RagCard(
        id="visa_asia_thailand",
        tags=["태국", "베트남", "말레이시아", "인도네시아", "비자", "서류"],
        fact="태국/말레이시아/베트남/인도네시아: 30~90일 무비자 관광 가능합니다. (90일 초과 시 비자 필요)"
    ),
    RagCard(
        id="visa_middle_east_uae",
        tags=["아랍에미리트", "사우디아아라비아", "비자", "중동", "서류"],
        fact="아랍에미리트(두바이): 90일 무비자 관광. / 사우디아라비아: 전자 비자(eVisa)를 발급받아야 합니다."
    ),
    RagCard(
        id="doc_passport_validity",
        tags=["여권", "유효기간", "서류", "필수"],
        fact="해외여행 시: 여권 유효기간이 최소 6개월 이상 남아있는지 확인해야 합니다."
    ),
    RagCard(
        id="doc_copy_safety",
        tags=["여권", "서류", "사본", "분실", "안전"],
        fact="여권/비자 사본: 여권, 비자 사본을 클라우드에 저장하거나 출력하여 별도로 보관하면 분실 시 유용합니다."
    ),
    
    # =========================================================
    # 2. 전압 및 플러그 (규격 공통 그룹) [총 8개]
    # =========================================================
    RagCard(
        id="jp_plug_voltage",
        tags=["일본", "전압", "플러그", "전기"],
        fact="일본: 전압 100V, 플러그 A형. 한국 전자제품(220V) 사용 시 돼지코 어댑터 필수."
    ),
    RagCard(
        id="us_plug_voltage",
        tags=["미국", "캐나다", "멕시코", "전압", "플러그", "전기"],
        fact="미국/캐나다/멕시코: 전압 120V, 플러그 A형. 한국 전자제품 사용 가능하나 충전이 느릴 수 있습니다."
    ),
    RagCard(
        id="eu_plug_voltage",
        tags=["프랑스", "이탈리아", "독일", "스페인", "네덜란드", "유럽", "전압", "플러그", "전기"],
        fact="유럽(솅겐): 전압 230V, 플러그 C/E/F형 혼용. 한국 220V와 비슷하나, 멀티 어댑터 준비를 권장합니다."
    ),
    RagCard(
        id="uk_plug_voltage",
        tags=["영국", "싱가포르", "홍콩", "전압", "플러그", "전기"],
        fact="영국/싱가포르/홍콩: 전압 230V, 플러그 G형(세모 모양 3구). 별도의 3구 어댑터 필수입니다."
    ),
    RagCard(
        id="au_plug_voltage",
        tags=["호주", "뉴질랜드", "전압", "플러그", "전기"],
        fact="호주/뉴질랜드: 전압 230V, 플러그 I형(경사진 V자 모양). 별도의 I형 어댑터 필수입니다."
    ),
    RagCard(
        id="tw_plug_voltage",
        tags=["대만", "전압", "플러그", "전기"],
        fact="대만: 전압 110V, 플러그 A/B형. 반드시 돼지코(110V용) 어댑터가 필요합니다."
    ),
    RagCard(
        id="cn_plug_voltage",
        tags=["중국", "전압", "플러그", "전기"],
        fact="중국: 전압 220V, 플러그 A/C/I형 혼용. 한국 제품 사용 가능하지만, 3구 플러그를 위한 어댑터 준비가 필요합니다."
    ),
    RagCard(
        id="in_plug_voltage",
        tags=["인도", "전압", "플러그", "전기"],
        fact="인도: 전압 230V, 플러그 C/D/M형 혼용. 멀티 어댑터 및 전압 불안정에 대비한 보조 배터리가 필수입니다."
    ),
    
    # =========================================================
    # 3. 날씨/건강 및 항공 [총 7개]
    # =========================================================
    RagCard(
        id="weather_rain_gear",
        tags=["비", "폭우", "날씨", "우비", "방수", "준비물"],
        fact="비 예보: 우산이나 우비, 휴대폰 방수팩, 가방 방수 커버, 방수 신발은 필수 준비물입니다."
    ),
    RagCard(
        id="weather_cold_gear",
        tags=["한파", "겨울", "의류", "방한", "핫팩"],
        fact="한파/겨울 여행: 내의, 기능성 발열 내피, 핫팩, 목도리, 장갑 등 보온 용품을 우선적으로 챙겨야 합니다."
    ),
    RagCard(
        id="weather_hot_gear",
        tags=["폭염", "여름", "더위", "선크림", "모자"],
        fact="폭염/여름 여행: 자외선 차단제(SPF 50+), 모자, 선글라스, 냉감 티셔츠, 휴대용 선풍기를 챙겨야 합니다."
    ),
    RagCard(
        id="health_meds_basic",
        tags=["의약품", "건강", "필수", "상비약"],
        fact="상비약: 소화제, 해열진통제, 지사제, 반창고, 밴드는 필수입니다. 현지 구매가 어려울 수 있습니다."
    ),
    RagCard(
        id="health_meds_prescription",
        tags=["의약품", "처방약", "규정", "서류"],
        fact="처방약: 복용 중인 약품은 영문 처방전과 함께 챙겨야 합니다. 마약류는 반입 규정을 확인해야 합니다."
    ),
    RagCard(
        id="health_air_travel",
        tags=["항공기", "비행", "건강", "준비물"],
        fact="장거리 비행: 안대, 목베개, 압박 스타킹, 이어플러그 등 기내 편의 용품을 챙겨야 합니다."
    ),
    RagCard(
        id="health_covid_global",
        tags=["전세계", "코로나", "건강", "위생", "마스크"],
        fact="글로벌 건강: 마스크, 손 소독제, 개인 위생 용품은 여전히 필수입니다. 입국 시 PCR/백신 증명서 요구 가능성이 있습니다."
    ),
    
    # =========================================================
    # 4. 활동/테마별 특수 장비 [총 4개]
    # =========================================================
    RagCard(
        id="activity_hiking_safety",
        tags=["하이킹", "등산", "활동", "안전", "장비"],
        fact="하이킹: 발목 보호대, 방충제(벌레 기피제), 등산화, 여분의 에너지바를 챙겨야 합니다."
    ),
    RagCard(
        id="activity_swim_gear",
        tags=["물놀이", "스노클링", "다이빙", "해변"],
        fact="물놀이: 수중 방수팩, 아쿠아슈즈, 물안경 또는 마스크, 래시가드를 챙겨야 합니다."
    ),
    RagCard(
        id="activity_business_needs",
        tags=["비즈니스", "출장", "회의", "복장", "업무"],
        fact="비즈니스 출장: 공식적인 회의를 위한 정장, 명함, 발표 자료 백업 USB는 필수입니다."
    ),
    RagCard(
        id="activity_cultural",
        tags=["박물관", "미술관", "학생", "할인", "활동"],
        fact="문화 활동: 국제 학생증(ISIC)이 있다면 박물관/미술관에서 할인을 받을 수 있습니다. 유효 기간을 확인하세요."
    ),
    
    # =========================================================
    # 5. 통신 및 금융/안전 (글로벌) [총 5개]
    # =========================================================
    RagCard(
        id="comm_sim_global",
        tags=["통신", "유심", "로밍", "이심", "폰"],
        fact="통신: 현지 유심(SIM) 또는 이심(eSIM)을 구매하는 것이 로밍보다 저렴합니다. 한국에서 미리 예약하면 공항에서 바로 사용할 수 있습니다."
    ),
    RagCard(
        id="finance_currency_tip",
        tags=["금융", "환전", "카드", "체크카드"],
        fact="금융: 비상시를 대비해 최소 2가지 이상의 결제 수단(신용카드, 체크카드, 현금)을 준비해야 합니다."
    ),
    RagCard(
        id="car_driver_license",
        tags=["운전", "차량", "렌트", "면허증", "서류"],
        fact="차량 렌트: 국제 운전면허증과 한국 운전면허증을 모두 소지해야 하며, 보험 가입 여부를 확인하세요."
    ),
    RagCard(
        id="safety_global_contact",
        tags=["안전", "응급", "연락처", "대사관", "전세계"],
        fact="비상연락망: 현지 대사관, 영사관, 여행자 보험사 연락처를 메모하거나 휴대전화에 저장해 두어야 합니다."
    ),
    RagCard(
        id="customs_duty_free",
        tags=["세관", "면세", "규정", "세금"],
        fact="면세품: 국내 입국 시 1인당 면세 한도(현재 $800)를 초과하지 않도록 주의해야 합니다."
    ),
    # 여행자 보험
    RagCard(
        id="finance_insurance",
        tags=["보험", "금융", "서류", "필수"],
        fact="여행자 보험: 여행 전 반드시 여행자 보험에 가입하고, 영문 가입 증명서를 출력하거나 모바일로 저장해야 합니다."
    ),
    # ATM 보안
    RagCard(
        id="finance_atm_security",
        tags=["금융", "카드", "안전", "현금", "복제"],
        fact="ATM 사용 시: 인적이 드문 곳의 ATM 사용은 피하고, 카드 복제 장치 부착 여부를 주의 깊게 확인해야 합니다."
    ),
    # 폰 언락
    RagCard(
        id="comm_phone_unlock",
        tags=["통신", "유심", "핸드폰", "장비"],
        fact="현지 유심 사용 시: 본인의 휴대폰이 통신사로부터 잠금 해제(언락) 상태인지 미리 확인해야 합니다. 언락 상태가 아니면 현지 유심을 사용할 수 없습니다."
    ),
    
    # =========================================================
    # 6. 국가별 생활 및 특수 예외 (위생/안전/문화) [총 17개]
    # =========================================================
    RagCard(
        id="jp_cash_tip",
        tags=["일본", "현금", "결제", "생활", "화폐"],
        fact="일본 생활: 현금 결제 비율이 높습니다. 주요 관광지를 벗어나면 카드 사용이 어려울 수 있으니 현금을 충분히 환전하세요."
    ),
    RagCard(
        id="th_food_tip",
        tags=["태국", "음식", "위생", "생활"],
        fact="태국 생활: 길거리 음식 섭취 시에는 반드시 익힌 음식을 먹고, 얼음물은 피하는 것이 좋습니다. 식중독을 예방해야 합니다."
    ),
    RagCard(
        id="tw_water_tip",
        tags=["대만", "물", "위생", "생활"],
        fact="대만 생활: 수돗물은 석회질이 포함되어 있어 그대로 마실 수 없습니다. 반드시 생수를 구매하거나 끓여 마셔야 합니다."
    ),
    RagCard(
        id="cn_sim_tip",
        tags=["중국", "통신", "인터넷", "VPN"],
        fact="중국 통신: 구글, 인스타그램 등 해외 서비스는 접속이 차단됩니다. 반드시 VPN 서비스를 미리 설치하고 테스트해야 합니다."
    ),
    RagCard(
        id="eu_cash_safety",
        tags=["유럽", "프랑스", "이탈리아", "스페인", "안전", "소매치기"],
        fact="유럽 도시 안전: 관광지에서 소매치기 위험이 높습니다. 가방을 몸 앞쪽으로 메고, 지갑은 깊숙이 보관해야 합니다."
    ),
    RagCard(
        id="us_tipping_culture",
        tags=["미국", "캐나다", "팁", "문화", "금융"],
        fact="미국/캐나다 문화: 식당, 택시 등 서비스업에서 팁(15~20%)은 의무입니다. 현금 또는 카드로 준비하세요."
    ),
    RagCard(
        id="tr_culture",
        tags=["튀르키예", "문화", "복장", "예외"],
        fact="튀르키예 문화: 이슬람 사원 방문 시 여성은 머리를 가릴 스카프, 남성은 반바지 착용을 피해야 합니다."
    ),
    RagCard(
        id="gr_water_tip",
        tags=["그리스", "물", "위생", "생활"],
        fact="그리스 생활: 아테네 등 일부 지역은 수돗물에 석회질이 많아 생수 구매를 권장합니다."
    ),
    RagCard(
        id="ae_culture",
        tags=["아랍에미리트", "중동", "두바이", "복장", "문화"],
        fact="아랍에미리트(두바이): 공공장소에서 과도한 노출은 피해야 합니다. 특히 라마단 기간에는 음식 섭취에 주의해야 합니다."
    ),
    RagCard(
        id="sa_culture",
        tags=["사우디아라비아", "중동", "복장", "문화"],
        fact="사우디아라비아: 여성은 공공장소에서 아바야 착용 등 엄격한 복장 규정을 준수해야 합니다."
    ),
    RagCard(
        id="au_customs_strict",
        tags=["호주", "뉴질랜드", "세관", "검역", "반입금지"],
        fact="호주/뉴질랜드 입국: 검역이 매우 엄격합니다. 식품, 식물, 씨앗 등은 반입이 금지되거나 반드시 신고해야 합니다."
    ),
    RagCard(
        id="br_safety_tip",
        tags=["브라질", "남미", "안전", "도난", "여행"],
        fact="브라질 안전: 대도시에서 도난 위험이 높습니다. 야간 외출은 삼가고, 고가품이나 현금을 노출하지 않아야 합니다."
    ),
    RagCard(
        id="in_hygiene_tip",
        tags=["인도", "위생", "물", "건강"],
        fact="인도 위생: 생수 외의 물은 마시지 않아야 하며, 길거리 음식과 껍질을 까지 않은 과일 섭취에 주의해야 합니다."
    ),
    RagCard(
        id="mx_cash_safety",
        tags=["멕시코", "남미", "안전", "현금"],
        fact="멕시코 안전: 현금은 소량만 소지하고, 카드를 사용할 경우 복제 위험에 주의해야 합니다."
    ),
    RagCard(
        id="kr_visa_tip",
        tags=["대한민국", "외국인", "비자", "서류"],
        fact="대한민국 입국: 90일 이상 체류 시 비자가 필수이며, 여권 만료일을 확인해야 합니다."
    ),
    RagCard(
        id="hu_water_tip",
        tags=["헝가리", "크로아티아", "물", "위생"],
        fact="헝가리/크로아티아: 수돗물 음용이 가능하지만, 석회질이 많으므로 예민한 경우 생수를 추천합니다."
    ),
    RagCard(
        id="ru_language_tip",
        tags=["러시아", "폴란드", "언어", "생활"],
        fact="러시아/폴란드 생활: 영어 사용이 제한적입니다. 번역 앱을 미리 준비하고, 대중교통 이용 시 현지어 표기에 익숙해져야 합니다."
    ),
]

# 3. 메인 인덱싱 함수
def embed_and_upload_data(data: List[RagCard]):
    if not qdrant_client:
        print("색인 생성 실패: Qdrant 클라이언트가 초기화되지 않았습니다.")
        return

    try:
        # 1. 컬렉션이 존재하는지 확인합니다.
        if qdrant_client.collection_exists(collection_name=QDRANT_COLLECTION):
            # 2. 존재하면 삭제합니다. (recreate 효과)
            qdrant_client.delete_collection(collection_name=QDRANT_COLLECTION)
            print(f"기존 컬렉션 '{QDRANT_COLLECTION}'을 삭제했습니다.")
            
        # 3. 새로운 컬렉션을 생성합니다. (DeprecationWarning 해결)
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE)
        )
        print(f"컬렉션 '{QDRANT_COLLECTION}'을 최신 표준으로 성공적으로 생성했습니다.")

    except UnexpectedResponse as e:
        print(f"Qdrant 연결 오류: 컬렉션을 생성할 수 없습니다. QDRANT_URL/API_KEY를 확인하세요. 세부 정보: {e}")
        return
    
    # ---------------------------
    # 임베딩 사용 준비
    # ---------------------------
    genai = get_embedding_client()
    if not genai:
        return  

    texts_to_embed = [f"Tags: {', '.join(item.tags)}. Fact: {item.fact}" for item in data]
    
    embedding_client = get_embedding_client()
    if not embedding_client:
        return

    print(f"총 {len(texts_to_embed)}개 문서를 {EMBEDDING_MODEL_NAME}를 사용하여 임베딩 중...")
    embeddings = []
    # ---------------------------
    # Google Generative AI 임베딩 호출
    # ---------------------------
    try:
        for text in texts_to_embed:
            result = genai.embed_content(
                model=EMBEDDING_MODEL_NAME,
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(result["embedding"])

    except Exception as e:
        print(f"❌ 임베딩 생성 오류: {e}")
        return

    # ---------------------------
    # Qdrant에 업로드
    # ---------------------------
    
    points = [
        models.PointStruct(
            id=str(uuid.uuid4()), 
            vector=embedding,
            payload=item.model_dump()
        )
        for item, embedding in zip(data, embeddings)
    ]

    qdrant_client.upsert(
        collection_name=QDRANT_COLLECTION,
        wait=True,
        points=points
    )
    print(f"총 {len(points)}개의 RAG 포인트를 Qdrant에 성공적으로 업로드했습니다.")

if __name__ == "__main__":
    embed_and_upload_data(RAG_DATA_SAMPLES)