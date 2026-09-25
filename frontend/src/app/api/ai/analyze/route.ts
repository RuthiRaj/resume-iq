import { NextRequest } from "next/server";
import { getOrCreateRequestId, forwardHeaders, createProxyResponse } from "@/lib/server-request-utils";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

/**
 * Next.js BFF Proxy Handler for AI Resume ATS Analysis.
 *
 * Forwards client requests, Firebase ID tokens, and correlation IDs directly to FastAPI backend:
 * Browser -> Next.js BFF (POST /api/ai/analyze) -> FastAPI (POST /api/v1/ai/analyze)
 */
export async function POST(req: NextRequest) {
  const reqId = getOrCreateRequestId(req);

  // 1. Read & Validate Authorization header
  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return createProxyResponse(
      {
        error:
          "Missing or invalid Authorization header. Expected 'Bearer <Firebase_ID_Token>'.",
      },
      401,
      reqId
    );
  }

  // 2. Parse Request JSON Body
  let body: any;
  try {
    body = await req.json();
  } catch {
    return createProxyResponse(
      { error: "Invalid JSON payload in request body." },
      400,
      reqId
    );
  }

  // 3. Forward request to FastAPI Backend
  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/ai/analyze`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: forwardHeaders(req, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });

    const contentType = backendResponse.headers.get("content-type") || "";
    let data: any;

    if (contentType.includes("application/json")) {
      data = await backendResponse.json();
    } else {
      const text = await backendResponse.text();
      data = { error: text || "Unexpected backend response." };
    }

    return createProxyResponse(data, backendResponse.status, reqId);
  } catch (err: any) {
    // Backend unreachable or network failure
    return createProxyResponse(
      {
        error:
          "AI backend service is temporarily unreachable. Please ensure the backend is running.",
      },
      503,
      reqId
    );
  }
}
