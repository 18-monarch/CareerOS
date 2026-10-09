// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/[...path]/route";
const context = { params: Promise.resolve({ path: ["auth", "me"] }) };
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
it("blocks production account access from Netlify previews", async () => {
  vi.stubEnv("CAREEROS_HOST_PLATFORM", "netlify");
  vi.stubEnv("CAREEROS_DEPLOY_CONTEXT", "deploy-preview");
  const upstream = vi.fn();
  vi.stubGlobal("fetch", upstream);
  const r = await GET(
    new NextRequest("https://preview.netlify.app/api/auth/me"),
    context,
  );
  expect(r.status).toBe(503);
  expect(upstream).not.toHaveBeenCalled();
});
it("rejects a wrong mutation origin before contacting the backend", async () => {
  vi.stubEnv("CAREEROS_HOST_PLATFORM", "netlify");
  vi.stubEnv("CAREEROS_DEPLOY_CONTEXT", "production");
  vi.stubEnv("FRONTEND_ORIGIN", "https://careeros.netlify.app");
  const upstream = vi.fn();
  vi.stubGlobal("fetch", upstream);
  const r = await POST(
    new NextRequest("https://careeros.netlify.app/api/auth/me", {
      method: "POST",
      headers: { origin: "https://attacker.example" },
    }),
    context,
  );
  expect(r.status).toBe(403);
  expect(upstream).not.toHaveBeenCalled();
});
it("forwards distinct secure cookies through the production gateway without caching", async () => {
  vi.stubEnv("CAREEROS_HOST_PLATFORM", "netlify");
  vi.stubEnv("CAREEROS_DEPLOY_CONTEXT", "production");
  vi.stubEnv("FRONTEND_ORIGIN", "https://careeros.netlify.app");
  vi.stubEnv("API_BASE_URL", "https://careeros-api.onrender.com");
  const response = new Response("{}", {
    headers: { "content-type": "application/json" },
  });
  response.headers.append(
    "set-cookie",
    "access=fixture; HttpOnly; Secure; Path=/",
  );
  response.headers.append("set-cookie", "csrf=fixture; Secure; Path=/");
  const upstream = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", upstream);
  const r = await GET(
    new NextRequest("https://careeros.netlify.app/api/auth/me"),
    context,
  );
  expect(r.status).toBe(200);
  expect(r.headers.getSetCookie()).toHaveLength(2);
  expect(r.headers.get("cache-control")).toBe("no-store");
  expect(upstream.mock.calls[0][0]).toBe(
    "https://careeros-api.onrender.com/auth/me",
  );
});
