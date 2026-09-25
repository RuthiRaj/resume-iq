import { NextRequest, NextResponse } from "next/server";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

export async function GET(req: NextRequest) {
  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "Missing or invalid Authorization header." },
      { status: 401 }
    );
  }

  const { searchParams } = new URL(req.url);
  const queryString = searchParams.toString();
  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/career/roadmaps${
    queryString ? `?${queryString}` : ""
  }`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "GET",
      headers: {
        Authorization: authHeader,
      },
    });

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch {
    return NextResponse.json(
      { error: "Career Roadmap backend service is unreachable." },
      { status: 503 }
    );
  }
}

export async function POST(req: NextRequest) {
  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "Missing or invalid Authorization header." },
      { status: 401 }
    );
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload." },
      { status: 400 }
    );
  }

  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/career/roadmaps/generate`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authHeader,
      },
      body: JSON.stringify(body),
    });

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch {
    return NextResponse.json(
      { error: "Career Roadmap synthesis backend service is unreachable." },
      { status: 503 }
    );
  }
}
