import { NextRequest, NextResponse } from "next/server";
import { getOrCreateRequestId, forwardHeaders, createProxyResponse } from "@/lib/server-request-utils";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  "http://localhost:8000";

export async function GET(req: NextRequest) {
  const reqId = getOrCreateRequestId(req);
  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return createProxyResponse(
      { error: "Missing or invalid Authorization header." },
      401,
      reqId
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
      headers: forwardHeaders(req),
    });

    const data = await backendResponse.json();
    return createProxyResponse(data, backendResponse.status, reqId);
  } catch {
    return createProxyResponse(
      { error: "Career Roadmap backend service is unreachable." },
      503,
      reqId
    );
  }
}

export async function POST(req: NextRequest) {
  const reqId = getOrCreateRequestId(req);
  const authHeader =
    req.headers.get("Authorization") || req.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return createProxyResponse(
      { error: "Missing or invalid Authorization header." },
      401,
      reqId
    );
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return createProxyResponse(
      { error: "Invalid JSON payload." },
      400,
      reqId
    );
  }

  const targetUrl = `${BACKEND_API_URL.replace(/\/+$/, "")}/api/v1/career/roadmaps/generate`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: forwardHeaders(req, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });

    const data = await backendResponse.json();
    return createProxyResponse(data, backendResponse.status, reqId);
  } catch {
    return createProxyResponse(
      { error: "Career Roadmap synthesis backend service is unreachable." },
      503,
      reqId
    );
  }
}
