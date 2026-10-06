let refreshing: Promise<unknown> | null = null;
function csrf() {
  return typeof document === "undefined"
    ? ""
    : document.cookie
        .split("; ")
        .find((c) => c.startsWith("career_csrf="))
        ?.split("=")[1] || "";
}
export async function api<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf(),
      ...init.headers,
    },
    credentials: "same-origin",
  });
  if (
    response.status === 401 &&
    retry &&
    !!csrf() &&
    !["/auth/login", "/auth/register", "/auth/refresh"].includes(path)
  ) {
    if (!refreshing)
      refreshing = api("/auth/refresh", { method: "POST" }, false).finally(
        () => {
          refreshing = null;
        },
      );
    try {
      await refreshing;
      return api<T>(path, init, false);
    } catch {
      window.dispatchEvent(new Event("auth-expired"));
    }
  }
  const data = await response.json();
  if (!response.ok) {
    const details = data.error?.fields
      ?.map(
        (f: { field: string; message: string }) => `${f.field}: ${f.message}`,
      )
      .join("; ");
    throw new Error(details || data.error?.message || "Request failed");
  }
  return data as T;
}
export const send = <T>(path: string, body: unknown, method = "POST") =>
  api<T>(path, { method, body: JSON.stringify(body) });
export const pretty = (s: string) =>
  s
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
export const date = (s?: string | null) =>
  s
    ? new Date(
        s.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(s) ? s : `${s}Z`,
      ).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Not published";
export const list = (s: string) =>
  s
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
export const statuses = [
  "DISCOVERED",
  "SAVED",
  "PLANNING_TO_APPLY",
  "APPLIED",
  "OA_RECEIVED",
  "OA_COMPLETED",
  "INTERVIEW",
  "FINAL_ROUND",
  "OFFER",
  "REJECTED",
  "WITHDRAWN",
  "EXPIRED",
];

export const localDateTime = (value?: string | null) => {
  if (!value) return "";
  const d = new Date(/Z$|[+-]\d{2}:\d{2}$/.test(value) ? value : value + "Z");
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
