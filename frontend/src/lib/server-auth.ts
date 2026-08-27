import { NextRequest } from "next/server";

export interface AuthenticatedUser {
  uid: string;
  email?: string;
}

/**
 * Verifies a Firebase ID token sent in the Authorization header.
 * Calls Google Identity Toolkit to cryptographically verify token signature, validity, and expiration.
 */
export async function authenticateServerRequest(req: NextRequest): Promise<AuthenticatedUser> {
  const authHeader = req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    const error = new Error("Missing or invalid Authorization header. Expected 'Bearer <Firebase ID Token>'.");
    (error as any).statusCode = 401;
    throw error;
  }

  const idToken = authHeader.replace("Bearer ", "").trim();
  if (!idToken) {
    const error = new Error("Bearer token is empty.");
    (error as any).statusCode = 401;
    throw error;
  }

  const apiKey =
    process.env.FIREBASE_API_KEY ||
    process.env.NEXT_PUBLIC_FIREBASE_API_KEY ||
    "";

  try {
    const response = await fetch(
      `https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken }),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData?.error?.message || "Invalid or expired Firebase ID token.";
      const error = new Error(`Authentication failed: ${errorMsg}`);
      (error as any).statusCode = 401;
      throw error;
    }

    const data = await response.json();
    const userRecord = data?.users?.[0];

    if (!userRecord || !userRecord.localId) {
      const error = new Error("No valid user record found for token.");
      (error as any).statusCode = 401;
      throw error;
    }

    return {
      uid: userRecord.localId,
      email: userRecord.email,
    };
  } catch (err: any) {
    if (err.statusCode) throw err;
    const authError = new Error(`Server authentication error: ${err.message}`);
    (authError as any).statusCode = 401;
    throw authError;
  }
}
