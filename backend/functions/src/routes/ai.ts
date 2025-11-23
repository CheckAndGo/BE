import type { Express, Request, Response } from "express";
import { db } from "../firebase";

// -------------------------------------------------------------------
// Firestore에서 trips 컬렉션에 들어있는 문서 타입
// -------------------------------------------------------------------
type TripForAiDoc = {
  title: string;
  country: string;
  city: string;
  startDate: string;
  endDate: string;
  status?: "active" | "archived" | "deleted";
  travelerCount?: number;
  budget?: number;
  theme?: string;
  purpose?: string;
  lodgingTypes?: string[];
  transportModes?: string[];
};

type GenerateChecklistRequestBody = {
  tripId?: string;
};

// -------------------------------------------------------------------
// 1) AI 서버로 보낼 Payload 타입 (AI 팀 ChecklistRequest 스키마와 맞춤)
// -------------------------------------------------------------------
type AiRequestPayload = {
  tripId: string;
  locale: string;
  destination: {
    country: string;
    city: string;
  };
  period: {
    startDate: string;
    endDate: string;
    nights: number;
    days: number;
  };
  travelers: {
    count: number;
  };
  budget: {
    rawInput: string;
  } | null;
  purpose: string;
  lodging: {
    type: string;
  } | null;
  transportation: {
    type: string;
  } | null;
};

// -------------------------------------------------------------------
// 2) AI가 돌려주는 응답 타입들 (느슨하게 정의)
// -------------------------------------------------------------------
type AiChecklistItemRaw = {
  id?: string;
  title: string;
  checked?: boolean;
  important?: boolean; // LLM이 직접 줄 수도 있음 (옵션)
  priority?: "LOW" | "MEDIUM" | "HIGH";
  requiresVerification?: boolean;
};

type AiChecklistCategoryBlock = {
  category?: string;
  items?: AiChecklistItemRaw[];
};

type AiChecklistResponse = {
  tripId?: string;
  items?: AiChecklistItemRaw[];
  checklist?: AiChecklistCategoryBlock[];
  // 그 외 progress, message 등 들어올 수 있음 → any로 무시
  [key: string]: any;
};

// -------------------------------------------------------------------
// 3) 우리가 DB/프론트에서 쓰는 체크리스트 타입
// -------------------------------------------------------------------
type ChecklistItem = {
  id: string;
  title: string;
  checked: boolean;
  important?: boolean;
};

type ChecklistDoc = {
  tripId: string;
  items: ChecklistItem[];
};

// -------------------------------------------------------------------
// 라우트 등록
// -------------------------------------------------------------------
export function registerAiRoutes(app: Express) {
  /**
   * POST /ai/checklist/generate
   * Body: { "tripId": "trp_123" }
   *
   * 1) trips/{tripId} 문서 조회
   * 2) AI 요청용 payload(AiRequestPayload) 생성
   * 3) AI 서버(/api/v1/llm/boost) 호출
   * 4) 응답을 평탄화해서 checklists 컬렉션에 저장/덮어쓰기
   * 5) { tripId, summary, items } 형태로 프론트에 응답
   */
  app.post("/ai/checklist/generate", async (req: Request, res: Response) => {
    try {
      const { tripId } = req.body as GenerateChecklistRequestBody;

      if (!tripId) {
        return res.status(400).json({ error: "tripId 는 필수입니다." });
      }

      // 1) trips/{tripId} 문서 조회
      const docRef = db.collection("trips").doc(tripId);
      const snap = await docRef.get();

      if (!snap.exists) {
        return res.status(404).json({ error: "Trip not found" });
      }

      const trip = snap.data() as TripForAiDoc;

      // 2) AI 서버 스펙에 맞게 payload 구성
      const startDateObj = new Date(trip.startDate);
      const endDateObj = new Date(trip.endDate);
      const diffTime = Math.abs(endDateObj.getTime() - startDateObj.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1; // 여행 "일" 수
      const nights = diffDays - 1;

      const payload: AiRequestPayload = {
        tripId,
        locale: "ko",
        destination: {
          country: trip.country,
          city: trip.city,
        },
        period: {
          startDate: trip.startDate,
          endDate: trip.endDate,
          nights,
          days: diffDays,
        },
        travelers: {
          count: trip.travelerCount ?? 1,
        },
        budget: trip.budget != null ? { rawInput: `${trip.budget}원` } : null,
        purpose: trip.purpose ?? "관광",
        lodging:
          trip.lodgingTypes && trip.lodgingTypes.length > 0
            ? { type: trip.lodgingTypes[0] }
            : null,
        transportation:
          trip.transportModes && trip.transportModes.length > 0
            ? { type: trip.transportModes[0] }
            : null,
      };

      // 3) AI 서버 호출
      //    - env 에 CHECKLIST_AI_URL 이 설정되어 있으면 그걸 쓰고,
      //    - 아니면 로컬 기본값(http://127.0.0.1:8000/api/v1/llm/boost)을 사용
      const aiUrl =
        process.env.CHECKLIST_AI_URL ??
        "http://127.0.0.1:8000/api/v1/llm/boost";

      const aiToken =
        process.env.CHECKLIST_AI_TOKEN ?? "test_token"; // 필요 없으면 Authorization 헤더 제거해도 됨

      const resp = await fetch(aiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${aiToken}`,
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const text = await resp.text();
        console.error("AI server error:", resp.status, text);
        return res
          .status(502)
          .json({ error: "AI 서버 호출에 실패했습니다." });
      }

      const aiJson = (await resp.json()) as AiChecklistResponse;

      // 4) 응답에서 items 평탄화
      let rawItems: AiChecklistItemRaw[] = [];

      if (Array.isArray(aiJson.items)) {
        rawItems = aiJson.items;
      } else if (Array.isArray(aiJson.checklist)) {
        rawItems = aiJson.checklist.flatMap((block) => block.items ?? []);
      }

      if (!rawItems.length) {
        console.error("AI response has no items:", aiJson);
        return res
          .status(502)
          .json({ error: "AI 응답에 checklist 항목이 없습니다." });
      }

      const baseTs = Date.now();
      let counter = 0;

      const items: ChecklistItem[] = rawItems
        .filter((raw) => raw.title && raw.title.trim())
        .map((raw) => {
          const id = raw.id ?? `item_${baseTs}_${++counter}`;
          const checked = raw.checked ?? false;

          // 🔥 중요도 계산 로직:
          // 1) LLM이 important를 명시하면 그 값 사용
          // 2) 없으면 priority === "HIGH" 이거나 requiresVerification === true 면 중요(true)
          let important: boolean;
          if (typeof raw.important === "boolean") {
            important = raw.important;
          } else {
            important =
              raw.priority === "HIGH" ||
              raw.requiresVerification === true;
          }

          return {
            id,
            title: raw.title.trim(),
            checked,
            important,
          };
        });

      // 5) checklists 컬렉션 upsert (기존 있으면 덮어쓰기)
      const existingSnap = await db
        .collection("checklists")
        .where("tripId", "==", tripId)
        .limit(1)
        .get();

      if (existingSnap.empty) {
        const checklistRef = db.collection("checklists").doc();
        const docData: ChecklistDoc = {
          tripId,
          items,
        };
        await checklistRef.set(docData);
      } else {
        const checklistRef = existingSnap.docs[0].ref;
        await checklistRef.set(
          {
            tripId,
            items,
          } as ChecklistDoc,
          { merge: false }
        );
      }

      // 진행률 계산 (현재는 checked 기준)
      const total = items.length;
      const done = items.filter((i) => i.checked).length;
      const progress = total > 0 ? done / total : 0;

      // 6) 프론트로 summary + items 응답
      return res.status(200).json({
        tripId,
        summary: {
          total,
          done,
          progress,
        },
        items,
      });
    } catch (err) {
      console.error("[POST /ai/checklist/generate] error:", err);
      return res.status(500).json({ error: "Internal Server Error" });
    }
  });
}
