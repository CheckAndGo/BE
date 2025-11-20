// src/routes/auth.ts
import type { Express, Request, Response } from "express";
import { auth, db, FieldValue } from "../firebase";

const FIREBASE_WEB_API_KEY =
  process.env.FIREBASE_WEB_API_KEY ??
  "AIzaSyD_9ZFaxgZaUfw5oUEDJYB3qqiJiqdKsS8"; // 필요하면 env에서 교체

// -------------------- 유틸 --------------------
function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// -------------------- 타입 --------------------
type SignupRequestBody = {
  name: string;
  email: string;
  password: string;
  agreeTerms: boolean;
};

type LoginRequestBody = {
  email: string;
  password: string;
};

// -------------------- 라우트 등록 함수 --------------------
export function registerAuthRoutes(app: Express) {
  // 회원가입
  app.post("/auth/signup", async (req: Request, res: Response) => {
    if (req.method !== "POST") {
      return res.status(405).send("Method Not Allowed");
    }

    const { name, email, password, agreeTerms } =
      req.body as SignupRequestBody;

    if (!name || !email || !password) {
      return res
        .status(400)
        .json({ error: "name, email, password 는 필수입니다." });
    }

    if (!validateEmail(email)) {
      return res.status(400).json({ error: "이메일 형식이 올바르지 않습니다." });
    }

    if (password.length < 8) {
      return res
        .status(400)
        .json({ error: "비밀번호는 8자 이상이어야 합니다." });
    }

    try {
      const userRecord = await auth.createUser({
        displayName: name,
        email,
        password,
      });

      await db.collection("users").doc(userRecord.uid).set({
        name,
        email,
        agreeTerms: !!agreeTerms,
        provider: "password",
        createdAt: FieldValue.serverTimestamp(),
      });

      const user = {
        id: userRecord.uid,
        name: userRecord.displayName ?? "",
        email: userRecord.email ?? "",
        emailVerified: userRecord.emailVerified,
      };

      return res.status(201).json({
        user,
        message: "Sign up successful. Please verify your email.",
      });
    } catch (err: any) {
      console.error("Signup error:", err);

      if (err.code === "auth/email-already-exists") {
        return res.status(409).json({ error: "이미 사용 중인 이메일입니다." });
      }

      return res.status(500).json({ error: "서버 오류가 발생했습니다." });
    }
  });

  // 로그인
  app.post("/auth/login", async (req: Request, res: Response) => {
    if (req.method !== "POST") {
      return res.status(405).send("Method Not Allowed");
    }

    const { email, password } = req.body as LoginRequestBody;

    if (!email || !password) {
      return res
        .status(400)
        .json({ error: "email, password 는 필수입니다." });
    }

    if (!FIREBASE_WEB_API_KEY) {
      console.error("Missing FIREBASE_WEB_API_KEY env");
      return res
        .status(500)
        .json({ error: "서버 설정 오류(FIREBASE_WEB_API_KEY)." });
    }

    try {
      const resp = await fetch(
        `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${FIREBASE_WEB_API_KEY}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            password,
            returnSecureToken: true,
          }),
        }
      );

      const data: any = await resp.json();

      if (!resp.ok) {
        const code = data?.error?.message ?? "UNKNOWN";
        console.error("Login error from IdentityToolkit:", code, data);

        if (code === "EMAIL_NOT_FOUND" || code === "INVALID_PASSWORD") {
          return res
            .status(401)
            .json({ error: "이메일 또는 비밀번호가 올바르지 않습니다." });
        }

        return res.status(500).json({ error: "로그인에 실패했습니다." });
      }

      const userRecord = await auth.getUser(data.localId);

      const user = {
        id: userRecord.uid,
        name: userRecord.displayName ?? "",
        email: userRecord.email ?? "",
        emailVerified: userRecord.emailVerified,
      };

      return res.status(200).json({
        accessToken: data.idToken,
        user,
      });
    } catch (err) {
      console.error("Login error:", err);
      return res.status(500).json({ error: "서버 오류가 발생했습니다." });
    }
  });
}
