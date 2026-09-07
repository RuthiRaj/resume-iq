import { NextRequest, NextResponse } from "next/server";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ variantId: string }> }
) {
  const { variantId } = await params;
  if (!/^[a-zA-Z0-9_\-]+$/.test(variantId)) {
    return NextResponse.json(
      { error: "Invalid variantId format." },
      { status: 400 }
    );
  }

  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "Missing or invalid Authorization header." },
      { status: 401 }
    );
  }

  const searchParams = req.nextUrl.searchParams;
  const rawFormat = searchParams.get("format") || "markdown";
  const format = ["markdown", "plain_text", "json"].includes(rawFormat) ? rawFormat : "markdown";

  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/variants/${variantId}/export?format=${encodeURIComponent(format)}`;

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
      { error: "Variants backend service is unreachable." },
      { status: 503 }
    );
  }
}
