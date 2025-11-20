// src/routes/trips.ts
import type { Express, Request, Response } from "express";
import { db } from "../firebase";

// ---------- Firestore 문서 타입 ----------
type TripDoc = {
  title: string;
  country: string;
  city: string;
  startDate: string; // "YYYY-MM-DD"
  endDate: string;   // "YYYY-MM-DD"
  flagEmoji?: string;
  status?: "active" | "archived" | "deleted";
};

type ChecklistItem = {
  id: string; 
  title: string;
  checked: boolean;
};

type ChecklistDoc = {
  tripId: string;
  items: ChecklistItem[];
};

// 프론트로 내려줄 최종 DTO
export type TripCardDTO = {
  id: string;
  title: string;
  country: string;
  city: string;
  startDate: string;
  endDate: string;
  nights: number;
  days: number;
  dDay: number;     // D-12 → 12
  flagEmoji: string;
  progress: number; // 0 ~ 1
};

// ---------- 유틸 ----------
function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function diffInDays(from: Date, to: Date): number {
  const msPerDay = 1000 * 60 * 60 * 24;
  const fromDay = startOfDay(from).getTime();
  const toDay = startOfDay(to).getTime();
  return Math.ceil((toDay - fromDay) / msPerDay);
}

async function getChecklistProgress(tripId: string): Promise<number> {
  const snap = await db
    .collection("checklists")
    .where("tripId", "==", tripId)
    .limit(1)
    .get();

  if (snap.empty) return 0;

  const data = snap.docs[0].data() as ChecklistDoc;
  const total = data.items.length;
  if (total === 0) return 0;

  const checked = data.items.filter((item) => item.checked).length;
  return checked / total;
}

async function toTripCardDTO(
  id: string,
  trip: TripDoc,
  today: Date
): Promise<TripCardDTO> {
  const start = new Date(trip.startDate);
  const end = new Date(trip.endDate);

  const nights = diffInDays(start, end);
  const days = nights + 1;
  const dDay = diffInDays(today, start);
  const progress = await getChecklistProgress(id);

  return {
    id,
    title: trip.title,
    country: trip.country,
    city: trip.city,
    startDate: trip.startDate,
    endDate: trip.endDate,
    nights,
    days,
    dDay,
    flagEmoji: trip.flagEmoji ?? "",
    progress,
  };
}

// ---------- 라우트 등록 ----------
export function registerTripRoutes(app: Express) {

    // 개발용: 더미 데이터 넣기
    app.post("/debug/seed-trips", async (req: Request, res: Response) => {
        try {
          const batch = db.batch();
          const now = Date.now();


          const tripRef1 = db.collection("trips").doc("trp_1");
          batch.set(tripRef1, {
              title: "도쿄 여행",
              country: "일본",
              city: "도쿄",
              startDate: "2026-03-15",
              endDate: "2026-03-20",
              flagEmoji: "🇯🇵",
              status: "active",
          });

          const checklistRef1 = db.collection("checklists").doc("chk_trp_1");
          batch.set(checklistRef1, {
            tripId: "trp_1",
            items: [
                { id: `item_${now}_1`, title: "비행기 예약", checked: true },
                { id: `item_${now}_2`, title: "숙소 예약", checked: true },
                { id: `item_${now}_3`, title: "여행자 보험", checked: false },
            ],
          });

          await batch.commit();

          return res.status(201).json({ message: "seeded demo trips" });
        } catch (err) {
          console.error("[POST /debug/seed-trips] error:", err);
          return res.status(500).json({ error: "Failed to seed trips" });
        }
    });

    // GET /trips?limit=10&status=active : 홈 카드
    app.get("/trips", async (req: Request, res: Response) => {
      try {
        const rawLimit = req.query.limit;
        const limit =
          typeof rawLimit === "string" ? parseInt(rawLimit, 10) || 10 : 10;

        const statusParam = req.query.status;
        const status =
          typeof statusParam === "string" && statusParam.length > 0
            ? statusParam
            : "active";

        const today = new Date();

        let query = db
          .collection("trips")
          .orderBy("startDate", "asc")
          .limit(limit);

        if (status === "active") {
          query = query.where("status", "==", "active");
        }

        const snapshot = await query.get();

        const items: TripCardDTO[] = [];
        for (const doc of snapshot.docs) {
          const data = doc.data() as TripDoc;
          const dto = await toTripCardDTO(doc.id, data, today);
          items.push(dto);
        }

        // D-Day 오름차순 정렬 (가까운 여행 먼저)
        items.sort((a, b) => a.dDay - b.dDay);

        return res.status(200).json({
          items,
          nextCursor: null, // 나중에 페이징 붙이면 cursor 넣기
        });
      } catch (err) {
        console.error("[GET /trips] error:", err);
        return res.status(500).json({ error: "Internal Server Error" });
      }
    });

    // POST /trips/:tripId/checklist : 체크리스트 항목 추가
    app.post("/trips/:tripId/checklist", async (req: Request, res: Response) => {
      try {
        const tripId = req.params.tripId;
        const { title } = req.body as {
          title?: string;
        };

        // title만 검증
        if (!title || typeof title !== "string" || !title.trim()) {
          return res
            .status(400)
            .json({ error: "title 은 필수입니다." });
        }

        const trimmedTitle = title.trim();

        const snap = await db
          .collection("checklists")
          .where("tripId", "==", tripId)
          .limit(1)
          .get();

        const newItemId = `item_${Date.now()}`;

        const newItem: ChecklistItem = {
          id: newItemId,
          title: trimmedTitle,
          checked: false,
        };

        let updatedItems: ChecklistItem[];

        if (snap.empty) {
          // 체크리스트 문서가 없으면 새로 생성
          const checklistRef = db.collection("checklists").doc();
          updatedItems = [newItem];

          await checklistRef.set({
            tripId,
            items: updatedItems,
          });
        } else {
          // 기존 문서가 있으면 items 배열에 push
          const doc = snap.docs[0];
          const data = doc.data() as ChecklistDoc;

          updatedItems = [...data.items, newItem];

          await doc.ref.update({
            items: updatedItems,
          });
        }

        const total = updatedItems.length;
        const done = updatedItems.filter((i) => i.checked).length;
        const progress = total > 0 ? done / total : 0;

        return res.status(201).json({
          tripId,
          summary: {
            total,
            done,
            progress,
          },
          items: updatedItems,
        });
      } catch (err) {
        console.error("[POST /trips/:tripId/checklist] error:", err);
        return res.status(500).json({ error: "Internal Server Error" });
      }
    });

    // GET /trips/trp_1/checklist : 체크리스트 조회
    app.get("/trips/:tripId/checklist", async (req: Request, res: Response) => {
      try {
        const tripId = req.params.tripId;

        const snap = await db
          .collection("checklists")
          .where("tripId", "==", tripId)
          .limit(1)
          .get();

        if (snap.empty) {
          return res.status(404).json({ error: "Checklist not found" });
        }

        const doc = snap.docs[0];
        const data = doc.data() as ChecklistDoc;

        const total = data.items.length;
        const done = data.items.filter((i) => i.checked).length;
        const progress = total > 0 ? done / total : 0;

        return res.status(200).json({
          tripId: data.tripId,
          summary: {
            total,
            done,
            progress,
          },
          items: data.items, 
        });
      } catch (err) {
        console.error("[GET /trips/:tripId/checklist] error:", err);
        return res.status(500).json({ error: "Internal Server Error" });
      }
    });

    // PATCH //trips/:tripId/checklist/:itemId : 체크리스트 항목 수정 (제목/완료 여부)
    app.patch("/trips/:tripId/checklist/:itemId",
      async(req: Request, res: Response) => {
        try {
          const {tripId, itemId} = req.params;
          const {title, checked} = req.body as {
            title?: string;
            checked?: boolean;
          };

          if(title === undefined && checked === undefined) {
            return res.status(400).json({error: "title 또는 checked 중 하나는 포함되어야 합니다."});
          }

          let newTitle: string | undefined = undefined;
          if(title !== undefined) {
            if(typeof title !== "string" || !title.trim()) {
              return res.status(400).json({ error: "title 이 비어있거나 문자열이 아닙니다." });
            }
            newTitle = title.trim();
          }

          // tripId 에 해당하는 체크리스트 문서 찾기
          const snap = await db
            .collection("checklists")
            .where("tripId", "==", tripId)
            .limit(1)
            .get();

          if(snap.empty) {
            return res.status(404).json({error: "Checklist not found"});
          }

          const doc = snap.docs[0];
          const data = doc.data() as ChecklistDoc;

          // 해당 itemId 를 가진 항목 찾기
          const items = data.items;
          const idx = items.findIndex((i) => i.id === itemId);

          if(idx === -1) {
            return res.status(404).json({error : "Checklist item not found" });
          }

          // 항목 업데이트
          const target = items[idx];
          const updatedItem: ChecklistItem = {
            ...target,
            ...(newTitle !== undefined ? { title: newTitle } : {}),
            ...(checked !== undefined ? { checked } : {}),
          };

          const updatedItems: ChecklistItem[] = [
            ...items.slice(0, idx),
            updatedItem,
            ...items.slice(idx + 1),
          ];

          await doc.ref.update({ items: updatedItems });

          const total = updatedItems.length;
          const done = updatedItems.filter((i) => i.checked).length;
          const progress = total > 0 ? done / total : 0; // 체크리스트 완료율 계산

          return res.status(200).json({
            tripId,
            summary: {
              total,
              done,
              progress,
            },
            items: updatedItems,
          });
        } catch (err) {
          console.error( "[PATCH /trips/:tripId/checklist/:itemId] error:", err);
          return res.status(500).json({ error: "Internal Server Error" });
        }
      }
    );

    // DELETE /trips/:tripId/checklist/:itemId : 체크리스트 항목 삭제
    app.delete(
      "/trips/:tripId/checklist/:itemId",
      async (req: Request, res: Response) => {
        try {
          const { tripId, itemId } = req.params;

          // tripId 에 해당하는 체크리스트 문서 찾기
          const snap = await db
            .collection("checklists")
            .where("tripId", "==", tripId)
            .limit(1)
            .get();

          if (snap.empty) {
            return res.status(404).json({ error: "Checklist not found" });
          }

          const doc = snap.docs[0];
          const data = doc.data() as ChecklistDoc;

          const beforeLength = data.items.length;
          const updatedItems = data.items.filter((i) => i.id !== itemId);

          // 길이가 안 줄었다 = 해당 itemId가 없었다
          if (updatedItems.length === beforeLength) {
            return res
              .status(404)
              .json({ error: "Checklist item not found" });
          }

          await doc.ref.update({ items: updatedItems });

          const total = updatedItems.length;
          const done = updatedItems.filter((i) => i.checked).length;
          const progress = total > 0 ? done / total : 0;

          return res.status(200).json({
            tripId,
            summary: {
              total,
              done,
              progress,
            },
            items: updatedItems,
          });
        } catch (err) {
          console.error(
            "[DELETE /trips/:tripId/checklist/:itemId] error:",
            err
          );
          return res.status(500).json({ error: "Internal Server Error" });
        }
      }
    );
}
