import type { NextConfig } from "next";
const config: NextConfig = {
  // Netlify's NETLIFY/CONTEXT variables are build-only. Bake only these
  // non-secret labels into the bundle for preview isolation.
  env: {
    CAREEROS_HOST_PLATFORM:
      process.env.NETLIFY === "true" ? "netlify" : "local",
    CAREEROS_DEPLOY_CONTEXT: process.env.CONTEXT || "local",
  },
  poweredByHeader: false,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline'" +
              (process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : "") +
              "; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
          },
        ],
      },
    ];
  },
};
export default config;
