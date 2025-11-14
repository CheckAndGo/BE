/**
 * Check&Go – Firebase Functions (v2, Seoul region)
 * - HTTPS 엔드포인트:
 *   0) GET  /ping               : 헬스체크
 *   1) POST /createTrip         : 여행(Trip) 생성
 *   2) POST /createEvent        : 여행 일정(Event) 추가
 *   3) POST /recommend          : (룰 기반) 체크리스트 생성
 *
 * Firestore 구조(초안):
 *   trips/{tripId}
 *     └─ events/{eventId}
 *     └─ items/{itemId}
 *   weatherSnapshots/{country_season}  // 국가×계절 캐시(간이)
 *
 * NOTE
 * - v2에선 functions.region(...).https.onRequest 대신
 *   setGlobalOptions({ region }) + onRequest(handler) 를 사용.
 * - v2 핸들러는 `void | Promise<void>`를 반환해야 하므로
 *   res.send / res.json 을 "호출만" 하고 값을 return 하지 않는다.
 */

import * as admin from "firebase-admin";
import { z } from "zod";
import { setGlobalOptions } from "firebase-functions/v2";
import { onRequest } from "firebase-functions/v2/https";
import { getFirestore, FieldValue, Timestamp } from "firebase-admin/firestore";


// ──────────────────────────────────────────────────────
// Firebase Admin 초기화 & 전역 옵션(리전: 서울) 고정
admin.initializeApp();
setGlobalOptions({ region: "asia-northeast3" });

// Firestore 핸들 & 서버 타임스탬프 헬퍼
const db = getFirestore();
const now = FieldValue.serverTimestamp; 


// ──────────────────────────────────────────────────────
// 0) 헬스체크(배포/에뮬레이터 동작 확인용)
//    - GET /ping → "pong"
export const ping = onRequest((_, res) : void => {
    res.send("pong");
});

// ──────────────────────────────────────────────────────
// 1) Trip 생성: POST /createTrip
//    createTrip — Trip 문서 생성
//    목적: 앱에서 “여행 만들기”를 누르면 Trip 엔터티를 발급
//    입력: { userId, title, country, startDate, endDate }
//    출력: { tripId }
//    요청 바디 런타임 검증(Zod)
const CreateTrip = z.object({
  userId: z.string(),     // 소유자 UID
  title: z.string(),      // 여행 제목
  country: z.string(),    // ISO 국가코드 등 ("KR","JP","GB"...)
  startDate: z.string(),  // "YYYY-MM-DD"
  endDate: z.string(),    // "
});

export const createTrip = onRequest(async (req, res): Promise<void> => {
    if(req.method !== "POST") {
        res.status(405).send("POST only");
        return;
    }
    try {
         // [역할] 요청 스키마 검증 → 계절 추론 → DB 저장 → ID 반환
        const body = CreateTrip.parse(req.body);
        const season = inferSeason(body.startDate); // [유틸] 월 기반 간이 계절 결정

        const doc = {
            ...body,
            season,         // "spring" | "summer" | "autumn" | "winter"
            createdAt: now(), 
            updatedAt: now(),
        };
        const ref = await db.collection("trips").add(doc);
        res.json({ tripId: ref.id });
    }catch (e: any) {
        console.error(e);
        res.status(400).json({ error: e.message });
    }
});

// ──────────────────────────────────────────────────────
// 2) Event 추가: POST /createEvent
//    createEvent — Trip 하위에 Event 추가
//    목적: 사용자가 여행 일정(날짜/제목/메모)을 추가
//    입력: { tripId, date, title, note? }
//    출력: { eventId }
const CreateEvent = z.object({
  tripId: z.string(),                // 부모 Trip ID
  date: z.string(),                  // "YYYY-MM-DD"
  title: z.string(),                 // 일정 제목
  note: z.string().optional().default(""), // 메모(선택)
});

export const createEvent = onRequest(async (req, res): Promise<void> => {
    if(req.method !== "POST") {
        res.status(405).send("POST only");
        return;
    }
    try {
        // [역할] Trip 하위 서브컬렉션(events)에 일정 한 건을 추가
        const { tripId, ...rest } = CreateEvent.parse(req.body);

        const ref = db.collection("trips").doc(tripId).collection("events").doc();
        await ref.set({ ...rest, createdAt: now(), updatedAt: now() });

        res.json({ eventId: ref.id });
    }catch(e: any) {
        console.error(e);
        res.status(400).json({error : e.message});
    }
});

// ──────────────────────────────────────────────────────
// 3) 추천(룰 베이스라인): POST /recommend
//    recommend — 룰 기반 체크리스트 생성
//    목적: Trip의 국가/계절(+간이 날씨버킷)로 기본 아이템 셋을 생성
//    흐름: Trip 로드 → 날씨 스냅샷(캐시) → ruleRecommend → items 서브컬렉션에 배치저장
//    입력: { tripId }
//    출력: { count, items[] }
const RecommendReq = z.object({ tripId: z.string() });

type Item = {
  category: string;       // "essential" | "clothes" | "weather" | ...
  name: string;           // 아이템 명
  qty: number;            // 수량
  source: "rule" | "ai";  // 추천 출처(룰/AI 병합 시 추적)
};

export const recommend = onRequest(async (req, res): Promise<void> => {
    if (req.method !== "POST") {
        res.status(405).send("POST only");
        return;
    }
    try {
        // [역할] Trip 조회 & 존재 검증
        const { tripId } = RecommendReq.parse(req.body);

        
        const snap = await db.collection("trips").doc(tripId).get();
        if(!snap.exists) {
            res.status(404).json({error: "trip not found"});
            return;
        }
        const trip = snap.data() as any;

        // [역할] 국가×계절 키로 날씨 캐시 조회/생성 (실서비스 전 임시)
        const key = `${trip.country}_${trip.season}`;
        const weather = await getOrCreateWeatherSnapshot(key);

        // 룰 기반 추천 생성
        const items: Item[] = ruleRecommend(trip, weather);

        // /trips/{tripId}/items 서브컬렉션에 배치 저장
        const batch = db.batch();
        const itemsCol = db.collection("trips").doc(tripId).collection("items");
        for(const it of items) {
            batch.set(itemsCol.doc(), {
                ...it,
                checked:false, // 초기값(미체크)
                createdAt: now(),
                updatedAt: now()
            });
        }
        await batch.commit();

        res.json({count : items.length, items});
    }catch(e: any) {
        console.error(e);
        res.status(400).json({error: e.message});
    }
});


// ──────────────────────────────────────────────────────
// 유틸: "YYYY-MM-DD"에서 월을 읽어 단순 계절 분류
function inferSeason(iso: string): "spring" | "summer" | "autumn" | "winter" {
  const m = Number(iso.slice(5, 7));
  if ([3, 4, 5].includes(m)) return "spring";
  if ([6, 7, 8].includes(m)) return "summer";
  if ([9, 10, 11].includes(m)) return "autumn";
  return "winter"; // 12, 1, 2
}

// 유틸: 국가×계절 캐시(12h TTL)
// - 실서비스에선 외부 날씨 API 연동 → bucket 계산 후 저장
async function getOrCreateWeatherSnapshot(key: string) {
  const ref = db.collection("weatherSnapshots").doc(key);
  const snap = await ref.get();
  const nowMs = Date.now();

  // 캐시 유효하면 그대로 반환
  if (snap.exists && snap.data()!.expiresAt?.toMillis() > nowMs) {
    return snap.data();
  }

  // 임시 데이터(기본값: normal)
  const data = {
    key,
    country: key.split("_")[0],
    season: key.split("_")[1],
    bucket: "normal", // TODO: "rainy" | "hot" | "cold" 등으로 확장
    expiresAt: Timestamp.fromMillis(nowMs + 12 * 60 * 60 * 1000),
  };
  await ref.set(data, { merge: true });
  return data;
}

// [유틸] 룰 기반 추천 (최소 가이드)
// - 계절/날씨 버킷에 따라 아이템을 가산
// - 추후 AI 추천과 병합 시 source 필드로 출처 구분
function ruleRecommend(trip: any, weather: any): Item[] {
  const items: Item[] = [
    { category: "essential",  name: "Passport",           qty: 1, source: "rule" },
    { category: "toiletries", name: "Toothbrush",         qty: 1, source: "rule" },
  ];
  if (trip.season === "summer") {
    items.push({ category: "clothes", name: "Short-sleeve T-shirts", qty: 3, source: "rule" });
  }
  if (trip.season === "winter") {
    items.push({ category: "clothes", name: "Thermal Underwear",     qty: 2, source: "rule" });
  }
  if (weather.bucket === "rainy") {
    items.push({ category: "weather", name: "Compact Umbrella",      qty: 1, source: "rule" });
  }
  return items;
}