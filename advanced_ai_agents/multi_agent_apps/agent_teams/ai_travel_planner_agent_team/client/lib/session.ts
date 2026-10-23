import { headers } from "next/headers";
import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

/** Returns the signed-in better-auth user id for this request, or null. */
export async function getSessionUserId(): Promise<string | null> {
  const session = await auth.api.getSession({ headers: await headers() });
  return session?.user?.id ?? null;
}

export function unauthorizedResponse() {
  return NextResponse.json(
    { success: false, message: "Authentication required" },
    { status: 401 }
  );
}

/** Headers for server-to-server calls to the FastAPI backend. */
export function backendHeaders(): Record<string, string> {
  const token = process.env.TRIPCRAFT_INTERNAL_API_TOKEN;
  return {
    "Content-Type": "application/json",
    ...(token ? { "X-TripCraft-Internal-Token": token } : {}),
  };
}
