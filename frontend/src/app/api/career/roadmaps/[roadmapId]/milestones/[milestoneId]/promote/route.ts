import { NextRequest, NextResponse } from "next/server";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ roadmapId: string; milestoneId: string }> }
) {
  const { roadmapId, milestoneId } = await params;
  if (
    !roadmapId ||
    !/^[a-zA-Z0-9_\-]+$/.test(roadmapId) ||
    !milestoneId ||
    !/^[a-zA-Z0-9_\-]+$/.test(milestoneId)
  ) {
    return NextResponse.json(
      { error: "Invalid roadmapId or milestoneId format." },
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

  const targetUrl = `${BACKEND_API_URL.replace(
    /\/+$/,
    ""
  )}/api/v1/career/roadmaps/${roadmapId}/milestones/${milestoneId}/promote`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        Authorization: authHeader,
      },
    });

    const data = await backendResponse.json();
    return NextResponse.json(data, { status: backendResponse.status });
  } catch {
    return NextResponse.json(
      { error: "Career Roadmap promotion backend service is unreachable." },
      { status: 503 }
    );
  }
}
