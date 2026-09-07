import { NextRequest, NextResponse } from "next/server";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ ingestionId: string }> }
) {
  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "Missing or invalid Authorization header." },
      { status: 401 }
    );
  }

  const { ingestionId } = await params;
  if (!ingestionId) {
    return NextResponse.json(
      { error: "Missing ingestionId path parameter." },
      { status: 400 }
    );
  }

  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/resumes/ingest/${ingestionId}`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "GET",
      headers: {
        Authorization: authHeader,
      },
    });

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Resume ingestion backend service is unreachable." },
      { status: 503 }
    );
  }
}
