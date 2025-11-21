import type { Express, Request, Response } from "express";
import { db } from "../firebase";

// trips 컬렉션에 들어갈 기본 형태 (기존 TripDoc에 theme, purpose만 추가했다고 보면 됨)
type TripDoc = {
  title: string;
  country: string;
  city: string;
  startDate: string; // "YYYY-MM-DD"
  endDate: string;   // "YYYY-MM-DD"
  flagEmoji?: string;

  // 홈/캘린더 공통에서 쓸 상태값
  status?: "active" | "archived" | "deleted";

  // 캘린더 카드용
  travelerCount?: number;      // 인원 수
  budget?: number;             // 예산(원 단위 등, 선택)
  theme?: string;              // "벚꽃 여행" 같은 한 줄 설명
  purpose?: string;            // "휴양", "관광" 등
  lodgingTypes?: string[];     // ["호텔", "게스트하우스", ...]
  transportModes?: string[];   // ["항공기", "자동차", ...]
};

type CreateTripRequestBody = {
  title?: string;
  country?: string;
  city?: string;
  startDate?: string;
  endDate?: string;
  travelerCount?: number;
  budget?: number;
  theme?: string;
  purpose?: string;
  lodgingTypes?: string[];
  transportModes?: string[];
};

// 캘린더 화면에 내려줄 DTO
export type CalendarTripDTO = {
  id: string;
  country: string;
  city: string;
  theme: string;        // 카드 중간 텍스트
  purposeTag: string;   // 아래 태그(관광/휴양/기타 ...)
  startDate: string;    // "YYYY-MM-DD"
  endDate: string;      // "YYYY-MM-DD"
};

// 날짜 formatting용 유틸
function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

// ---------- 라우트 등록 ----------
export function registerCalendarRoutes(app: Express) {

  // POST /trips : 새 여행 생성
  app.post("/trips", async(req: Request, res: Response) => {
    try {
      const {
        title,
        country,
        city,
        startDate,
        endDate,
        travelerCount,
        budget,
        theme,
        purpose,
        lodgingTypes,
        transportModes,
      } = req.body as CreateTripRequestBody;

      // 필수값 체크
      if (!title || !country || !city || !startDate || !endDate) {
        return res.status(400).json({
          error:
            "title, country, city, startDate, endDate 는 필수입니다.",
        });
      }

      // 날짜 대충이라도 검증
      const start = new Date(startDate);
      const end = new Date(endDate);
      if (isNaN(start.getTime()) || isNaN(end.getTime()) || start > end) {
        return res
          .status(400)
          .json({ error: "startDate / endDate 가 올바르지 않습니다." });
      }

      // Firestore에 저장할 문서 데이터
      const tripData: TripDoc = {
        title,
        country,
        city,
        startDate,
        endDate,
        status: "active",
        // 선택값들
        travelerCount,
        budget,
        theme,
        purpose,
        lodgingTypes,
        transportModes,
      };

      const docRef = db.collection("trips").doc();
      await docRef.set(tripData);

      // 홈 카드 형식으로 응답
      return res.status(201).json({
        id: docRef.id,
        ...tripData,
      });
    } catch (err) {
      console.error("[POST /trips] error:", err);
      return res.status(500).json({ error: "Internal Server Error" });
    }
  });

  // --------------------------------------------------
  // PATCH /trips/:tripId : 여행 정보 부분 수정 (1~4단계)
  // --------------------------------------------------
  app.patch("/trips/:tripId", async (req: Request, res: Response) => {
    try {
      const { tripId } = req.params;
      const body = req.body as CreateTripRequestBody;

      // 바꿀 게 아무 것도 없으면 에러
      if (!body || Object.keys(body).length === 0) {
        return res
          .status(400)
          .json({ error: "수정할 필드가 최소 1개 이상 필요합니다." });
      }

      // 날짜가 들어왔다면 간단 검증
      if (body.startDate || body.endDate) {
        const start = body.startDate ? new Date(body.startDate) : undefined;
        const end = body.endDate ? new Date(body.endDate) : undefined;

        if (
          (start && isNaN(start.getTime())) ||
          (end && isNaN(end.getTime())) ||
          (start && end && start > end)
        ) {
          return res
            .status(400)
            .json({ error: "startDate / endDate 가 올바르지 않습니다." });
        }
      }

      const docRef = db.collection("trips").doc(tripId);
      const snap = await docRef.get();

      if (!snap.exists) {
        return res.status(404).json({ error: "Trip not found" });
      }

      // body 에 있는 필드만 업데이트
      const allowedFields: (keyof CreateTripRequestBody)[] = [
        "title",
        "country",
        "city",
        "startDate",
        "endDate",
        "travelerCount",
        "budget",
        "theme",
        "purpose",
        "lodgingTypes",
        "transportModes",
      ];

      const updates: Partial<TripDoc> = {};
      for (const key of allowedFields) {
        const value = body[key];
        if (value !== undefined) {
          (updates as any)[key] = value;
        }
      }

      if (Object.keys(updates).length === 0) {
        return res
          .status(400)
          .json({ error: "업데이트할 유효한 필드가 없습니다." });
      }

      await docRef.update(updates);

      const updatedSnap = await docRef.get();
      const updatedData = updatedSnap.data() as TripDoc;

      return res.status(200).json({
        id: updatedSnap.id,
        ...updatedData,
      });
    } catch (err) {
      console.error("[PATCH /trips/:tripId] error:", err);
      return res.status(500).json({ error: "Internal Server Error" });
    }
  });

  // --------------------------------------------------
  // GET /trips/:tripId : 여행 상세 조회 (3단계 상단 카드용)
  // --------------------------------------------------
  app.get("/trips/:tripId", async (req: Request, res: Response) => {
    try {
      const { tripId } = req.params;

      const docRef = db.collection("trips").doc(tripId);
      const snap = await docRef.get();

      if (!snap.exists) {
        return res.status(404).json({ error: "Trip not found" });
      }

      const data = snap.data() as TripDoc;

      return res.status(200).json({
        id: snap.id,
        ...data,
      });
    } catch (err) {
      console.error("[GET /trips/:tripId] error:", err);
      return res.status(500).json({ error: "Internal Server Error" });
    }
  });

  /* - 특정 연/월에 시작하는 여행 목록
  * - 기본 status=active
  * - month는 1~12
  */
  // GET /calendar/trips?year=2026&month=3&status=active
  app.get("/calendar/trips", async (req: Request, res: Response) => {
      try {
      const { year: yearParam, month: monthParam, status: statusParam } =
          req.query;

      if (typeof yearParam !== "string" || typeof monthParam !== "string") {
          return res.status(400).json({
          error: "year, month 쿼리스트링이 필요합니다. 예: ?year=2026&month=3",
          });
      }

      const year = parseInt(yearParam, 10);
      const month = parseInt(monthParam, 10); // 1~12 기대

      if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12) {
          return res
          .status(400)
          .json({ error: "year 또는 month 값이 올바르지 않습니다." });
      }

      const status =
          typeof statusParam === "string" && statusParam.length > 0
          ? statusParam
          : "active";

      const monthStr = pad2(month);
      const startDateStr = `${year}-${monthStr}-01`;
      const lastDay = new Date(year, month, 0).getDate(); // 해당 달의 마지막 날
      const endDateStr = `${year}-${monthStr}-${pad2(lastDay)}`;

      // startDate가 해당 월 사이에 있는 여행들만 조회
      // status는 active만 (기본값)
      let query = db
          .collection("trips")
          .where("status", "==", status)
          .where("startDate", ">=", startDateStr)
          .where("startDate", "<=", endDateStr)
          .orderBy("startDate", "asc");

      const snapshot = await query.get();

      const items: CalendarTripDTO[] = [];
      for (const doc of snapshot.docs) {
          const data = doc.data() as TripDoc;

          items.push({
          id: doc.id,
          country: data.country,
          city: data.city,
          theme: data.theme ?? "",          // 없으면 빈 문자열
          purposeTag: data.purpose ?? "",   // 없으면 빈 문자열
          startDate: data.startDate,
          endDate: data.endDate,
          });
      }

      return res.status(200).json({
          items,
      });
      } catch (err) {
      console.error("[GET /calendar/trips] error:", err);
      return res.status(500).json({ error: "Internal Server Error" });
      }
  });

  /**
   * DELETE /calendar/trips/:tripId
   *
   * - 여행 계획 삭제 (캘린더/홈에서 모두 사라지게)
   * - 실제 삭제 대신 status="deleted" 로 soft delete 처리
   */
  app.delete(
    "/calendar/trips/:tripId",
    async (req: Request, res: Response) => {
      try {
        const { tripId } = req.params;

        const docRef = db.collection("trips").doc(tripId);
        const snap = await docRef.get();

        if (!snap.exists) {
          return res.status(404).json({ error: "Trip not found" });
        }

        // soft delete
        await docRef.update({ status: "deleted" });

        // 캘린더/홈 조회는 status=active 만 보도록 되어 있으니
        // 이후부터는 노출되지 않음
        return res.status(204).send(); // 바디 없음
      } catch (err) {
        console.error("[DELETE /calendar/trips/:tripId] error:", err);
        return res.status(500).json({ error: "Internal Server Error" });
      }
    }
  );
}
