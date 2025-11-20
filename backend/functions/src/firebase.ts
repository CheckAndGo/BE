// src/firebase.ts
import { initializeApp, getApps } from "firebase-admin/app";
import { getFirestore, FieldValue } from "firebase-admin/firestore";
import { getAuth } from "firebase-admin/auth";

// 여러 번 initialize 되는 것 방지
if (!getApps().length) {
  initializeApp();
}

export const db = getFirestore();
export const auth = getAuth();
export { FieldValue };
