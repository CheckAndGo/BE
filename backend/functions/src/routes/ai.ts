// import type { Express, Request, Response } from "express";
// import { db } from "../firebase";

// // LLM용으로 뽑아낼 trip 문서 타입 (trips 컬렉션 구조와 맞추기)
// type TripForAiDoc = {
//   title: string;
//   country: string;
//   city: string;
//   startDate: string;
//   endDate: string;
//   status?: "active" | "archived" | "deleted";
//   travelerCount?: number;
//   budget?: number;
//   theme?: string;
//   purpose?: string;
//   lodgingTypes?: string[];
//   transportModes?: string[];
// };

// type GenerateChecklistRequestBody = {
//   tripId?: string;
// };

// // LLM으로 넘길 최종 페이로드 타입 payload (참고용)
// export type ChecklistGeneratePayload = {
//   title: string;
//   country: string;
//   city: string;
//   startDate: string;
//   endDate: string;
//   travelerCount: number;
//   budget: number | null;
//   theme: string | null;
//   purpose: string | null;
//   lodgingTypes: string[];
//   transportModes: string[];
//   status: string;
// };


// // 라우트 등록 함수
// export function registerAiRoutes(app: Express) {
//   /**
//    * POST /ai/checklist/generate
//    * Body: { "tripId": "trp_123" }
//    *
//    * 1) trips/{tripId} 문서 조회
//    * 2) LLM에 넘길 JSON(payload) 생성
//    * 3) (지금은) payload 를 그대로 응답으로 내려줌
//    *    → 나중에 이 자리에서 LLM HTTP 호출 붙이면 됨
//    */
//   app.post("/ai/checklist/generate", async (req: Request, res: Response) => {
//     try {
//       const { tripId } = req.body as GenerateChecklistRequestBody;

//       if (!tripId) {
//         return res.status(400).json({ error: "tripId 는 필수입니다." });
//       }

//       const docRef = db.collection("trips").doc(tripId);
//       const snap = await docRef.get();

//       if (!snap.exists) {
//         return res.status(404).json({ error: "Trip not found" });
//       }

//       const trip = snap.data() as TripForAiDoc;

//       // LLM에 넘길 JSON 형식으로 가공
//       const payload: ChecklistGeneratePayload = {
//         title: trip.title,
//         country: trip.country,
//         city: trip.city,
//         startDate: trip.startDate,
//         endDate: trip.endDate,
//         travelerCount: trip.travelerCount ?? 1,
//         budget: trip.budget ?? null,
//         theme: trip.theme ?? null,
//         purpose: trip.purpose ?? null,
//         lodgingTypes: trip.lodgingTypes ?? [],
//         transportModes: trip.transportModes ?? [],
//         status: trip.status ?? "active",
//       };

//       // 🔻 여기서 실제 LLM HTTP 호출을 붙이면 됨
//       // 예시:
//       //
//       // const resp = await fetch(process.env.CHECKLIST_LLM_URL!, {
//       //   method: "POST",
//       //   headers: { "Content-Type": "application/json" },
//       //   body: JSON.stringify(payload),
//       // });
//       // const llmResult = await resp.json();
//       //
//       // return res.status(200).json({
//       //   tripId,
//       //   payload,
//       //   checklist: llmResult.checklist,
//       // });

//       // 일단은 payload만 응답으로 내려서 Postman / 프론트에서 확인
//       return res.status(200).json({
//         tripId,
//         payload,
//       });
//     } catch (err) {
//       console.error("[POST /ai/checklist/generate] error:", err);
//       return res.status(500).json({ error: "Internal Server Error" });
//     }
//   });
// }


import type { Express, Request, Response } from "express";
import { db } from "../firebase";

// LLM용으로 뽑아낼 trip 문서 타입 (trips 컬렉션 구조와 맞추기)
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

// LLM으로 넘길 최종 페이로드 타입 payload
export type ChecklistGeneratePayload = {
  title: string;
  country: string;
  city: string;
  startDate: string;
  endDate: string;
  travelerCount: number;
  budget: number | null;
  theme: string | null;
  purpose: string | null;
  lodgingTypes: string[];
  transportModes: string[];
  status: string;
};

// ===== 아래 타입들은 "나중에" LLM 결과를 체크리스트에 저장할 때 쓸 예정 =====

// LLM 이 돌려주는 raw 형식
type AiChecklistItemRaw = {
  id?: string;
  title: string;
  checked?: boolean;
  important?: boolean; 
};

type AiChecklistResponse = {
  tripId?: string;
  items: AiChecklistItemRaw[];
};

// 우리가 DB/프론트에서 쓰는 ChecklistItem
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

// 라우트 등록 함수
export function registerAiRoutes(app: Express) {
  /**
   * POST /ai/checklist/generate
   * Body: { "tripId": "trp_123" }
   *
   * 1) trips/{tripId} 문서 조회
   * 2) LLM에 넘길 JSON(payload) 생성
   * 3) (지금은) payload 만 응답으로 내려줌
   *    → 나중에 주석된 LLM HTTP 호출 코드로 교체하면 됨
   */
  app.post("/ai/checklist/generate", async (req: Request, res: Response) => {
    try {
      const { tripId } = req.body as GenerateChecklistRequestBody;

      if (!tripId) {
        return res.status(400).json({ error: "tripId 는 필수입니다." });
      }

      // 1) trip 문서 조회
      const docRef = db.collection("trips").doc(tripId);
      const snap = await docRef.get();

      if (!snap.exists) {
        return res.status(404).json({ error: "Trip not found" });
      }

      const trip = snap.data() as TripForAiDoc;

      // 2) LLM에 넘길 JSON 형식으로 가공
      const payload: ChecklistGeneratePayload = {
        title: trip.title,
        country: trip.country,
        city: trip.city,
        startDate: trip.startDate,
        endDate: trip.endDate,
        travelerCount: trip.travelerCount ?? 1,
        budget: trip.budget ?? null,
        theme: trip.theme ?? null,
        purpose: trip.purpose ?? null,
        lodgingTypes: trip.lodgingTypes ?? [],
        transportModes: trip.transportModes ?? [],
        status: trip.status ?? "active",
      };

      // 🔹 지금은 간단 테스트용: payload만 프론트/포스트맨으로 돌려줌
      //    → 여기까지만 있어도 Postman 으로 end-to-end 흐름 확인 가능
      return res.status(200).json({
        tripId,
        payload,
      });

      /* 
      🔻🔻🔻  여기부터는 "나중에" LLM 서버 URL 나오면 사용할 코드 예시 🔻🔻🔻

      const aiUrl = process.env.CHECKLIST_AI_URL;
      if (!aiUrl) {
        console.error("Missing CHECKLIST_AI_URL env");
        return res
          .status(500)
          .json({ error: "CHECKLIST_AI_URL 환경변수가 없습니다." });
      }

      // 3) LLM HTTP API 호출
      const resp = await fetch(aiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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

      if (!aiJson.items || !Array.isArray(aiJson.items)) {
        console.error("AI response malformed:", aiJson);
        return res
          .status(502)
          .json({ error: "AI 응답 형식이 올바르지 않습니다." });
      }

      // 4) LLM 응답 → ChecklistItem 배열로 normalize
      const baseTs = Date.now();
      let counter = 0;

      const items: ChecklistItem[] = aiJson.items
        .filter((raw) => raw.title && raw.title.trim())
        .map((raw) => {
          const id = raw.id ?? `item_${baseTs}_${++counter}`;
          const checked = raw.checked ?? false;
          const important = raw.important ?? false; // ✅ 기본값 false

          return {
            id,
            title: raw.title.trim(),
            checked,
            important,
          };
        });

      // 5) checklists 컬렉션에 upsert (기존 있으면 덮어쓰기)
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
          { merge: false } // 통째로 덮어쓰기
        );
      }

      // 진행률 계산
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

      🔺🔺🔺 여기까지 LLM 연동용 코드, URL 나오면 위의 return 을 사용하도록 바꾸면 됨 🔺🔺🔺
      */
    } catch (err) {
      console.error("[POST /ai/checklist/generate] error:", err);
      return res.status(500).json({ error: "Internal Server Error" });
    }
  });
}

