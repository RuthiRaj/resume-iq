import { NextRequest } from "next/server";
import { getOrCreateRequestId, forwardHeaders, createProxyResponse } from "@/lib/server-request-utils";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

/**
 * Next.js BFF Proxy Handler for Workspace ATS Analysis Retrieval.
 *
 * Forwards client requests, Firebase ID tokens, and correlation IDs directly to FastAPI backend:
 * Browser -> Next.js BFF (GET /api/ai/workspace-analysis) -> FastAPI (GET /api/v1/ai/workspace-analysis)
 */
export async function GET(req: NextRequest) {
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

  // 2. Forward request to FastAPI Backend
  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/ai/workspace-analysis`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "GET",
      headers: forwardHeaders(req),
    });

    const contentType = backendResponse.headers.get("content-type") || "";
    let data: any;

    if (contentType.includes("application/json")) {
      data = await backendResponse.json();
    } else {
      const text = await backendResponse.text();
      try {
        data = JSON.parse(text);
      } catch {
        data = { error: text || "Invalid response from upstream service." };
      }
    }

    return createProxyResponse(data, backendResponse.status, reqId);
  } catch {
    return createProxyResponse(
      {
        error:
          "AI Workspace Analysis service is temporarily unavailable. Please retry in a few moments.",
      },
      503,
      reqId
    );
  }
}
