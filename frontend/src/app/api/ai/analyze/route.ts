import { NextRequest, NextResponse } from "next/server";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

/**
 * Next.js BFF Proxy Handler for AI Resume ATS Analysis.
 *
 * Forwards client requests and Firebase ID tokens directly to the FastAPI backend:
 * Browser -> Next.js BFF (POST /api/ai/analyze) -> FastAPI (POST /api/v1/ai/analyze)
 */
export async function POST(req: NextRequest) {
  // 1. Read & Validate Authorization header
  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      {
        error:
          "Missing or invalid Authorization header. Expected 'Bearer <Firebase_ID_Token>'.",
      },
      { status: 401 }
    );
  }

  // 2. Parse Request JSON Body
  let body: any;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload in request body." },
      { status: 400 }
    );
  }

  // 3. Forward request to FastAPI Backend
  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/ai/analyze`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authHeader,
      },
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

    return NextResponse.json(data, { status: backendResponse.status });
  } catch (err: any) {
    // Backend unreachable or network failure
    return NextResponse.json(
      {
        error:
          "AI backend service is temporarily unreachable. Please ensure the backend is running.",
      },
      { status: 503 }
    );
  }
}
