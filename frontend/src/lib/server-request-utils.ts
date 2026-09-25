import { NextRequest, NextResponse } from "next/server";

export function getOrCreateRequestId(req: NextRequest): string {
  const incoming = req.headers.get("x-request-id") || req.headers.get("X-Request-ID");
  if (incoming && incoming.trim() && incoming.length <= 128 && /^[A-Za-z0-9_\-]+$/.test(incoming.trim())) {
    return incoming.trim();
  }
  return `req_${crypto.randomUUID().replace(/-/g, "")}`;
}

export function forwardHeaders(req: NextRequest, extraHeaders?: Record<string, string>): Record<string, string> {
  const authHeader = req.headers.get("Authorization") || req.headers.get("authorization") || "";
  const requestId = getOrCreateRequestId(req);

  const headers: Record<string, string> = {
    "X-Request-ID": requestId,
    ...extraHeaders,
  };

  if (authHeader) {
    headers["Authorization"] = authHeader;
  }

  return headers;
}

export function createProxyResponse(
  data: any,
  status: number,
  requestId: string,
  extraHeaders?: Record<string, string>
): NextResponse {
  const headers = new Headers();
  headers.set("X-Request-ID", requestId);
  if (extraHeaders) {
    for (const [k, v] of Object.entries(extraHeaders)) {
      headers.set(k, v);
    }
  }

  // Ensure error bodies have request_id attached for UI reference
  if (data && typeof data === "object" && (status >= 400 || "error" in data || "detail" in data)) {
    if (!data.request_id) {
      data.request_id = requestId;
    }
  }

  return NextResponse.json(data, { status, headers });
}
