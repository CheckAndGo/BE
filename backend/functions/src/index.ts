// src/index.ts
import "dotenv/config";
import express from "express";
import cors from "cors";
import { onRequest } from "firebase-functions/v2/https";

// 라우트 등록 함수 import
import { registerAuthRoutes } from "./routes/auth";
import { registerTripRoutes } from "./routes/trips";
import { registerCalendarRoutes } from "./routes/calendar";
import { registerAiRoutes } from "./routes/ai"; 

// --- Express 앱 설정 ---
const app = express();
app.use(cors({ origin: true }));
app.use(express.json());

// --- 라우트 묶어서 등록 ---
registerAuthRoutes(app);
registerTripRoutes(app);
registerCalendarRoutes(app);
registerAiRoutes(app);

// --- Cloud Functions Export ---
export const api = onRequest(
  { region: "asia-northeast3" },
  (req, res) => app(req, res)
);
