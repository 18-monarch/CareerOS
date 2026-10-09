import { NextRequest, NextResponse } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Same-origin gateway: tokens stay in HttpOnly cookies on the frontend's host.
async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  // Preview hosts must not read or mutate the private production account.
  if (
    process.env.CAREEROS_HOST_PLATFORM === "netlify" &&
    process.env.CAREEROS_DEPLOY_CONTEXT !== "production"
  )
    return NextResponse.json(
      {
        error: {
          message:
            "CareerOS account access is disabled on deploy previews. Open the production site.",
        },
      },
      { status: 503 },
    );
  const { path } = await params;
  if (path.some((p) => !/^[a-zA-Z0-9_-]+$/.test(p)))
    return NextResponse.json(
      { error: { message: "Invalid path" } },
      { status: 400 },
    );
  const origin = process.env.FRONTEND_ORIGIN || "http://localhost:3000";
  if (
    !["GET", "HEAD", "OPTIONS"].includes(request.method) &&
    request.headers.get("origin") !== origin
  )
    return NextResponse.json(
      { error: { message: "Origin not allowed" } },
      { status: 403 },
    );
  const base = process.env.API_BASE_URL || "http://127.0.0.1:8000";
  const headers = new Headers();
  for (const name of ["content-type", "cookie", "x-csrf-token", "origin"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (Number(request.headers.get("content-length") || 0) > 1048576)
    return NextResponse.json(
      { error: { message: "Request too large" } },
      { status: 413 },
    );
  try {
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : await request.arrayBuffer();
    if (body && body.byteLength > 1048576)
      return NextResponse.json(
        { error: { message: "Request too large" } },
        { status: 413 },
      );
    const upstream = await fetch(
      `${base}/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(
          process.env.CAREEROS_HOST_PLATFORM === "netlify" ? 25000 : 90000,
        ),
      },
    );
    const result = new NextResponse(upstream.body, { status: upstream.status });
    for (const name of ["content-type", "x-request-id", "retry-after"]) {
      const value = upstream.headers.get(name);
      if (value) result.headers.set(name, value);
    }
    result.headers.set("Cache-Control", "no-store");
    for (const cookie of upstream.headers.getSetCookie())
      result.headers.append("set-cookie", cookie);
    return result;
  } catch {
    return NextResponse.json(
      {
        error: {
          message:
            "CareerOS API is unavailable or waking up. Wait about a minute and try again. A queued discovery check will continue independently.",
        },
      },
      { status: 502 },
    );
  }
}
export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};
