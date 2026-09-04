import { existsSync } from "node:fs";
import type { NextConfig } from "next";

// The Django API has no CORS layer, so the browser only ever talks to this Next
// server (same origin) and /api/* is proxied here. Session + CSRF cookies therefore
// live on the frontend origin and the auth middleware can see `sessionid`.
// Inside compose the target is the backend service (Django ALLOWED_HOSTS includes "backend");
// override with API_PROXY_URL when the API lives elsewhere.
const IN_DOCKER = existsSync("/.dockerenv");
const API_PROXY_URL =
  process.env.API_PROXY_URL ?? (IN_DOCKER ? "http://backend:8000" : "http://localhost:8000");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: __dirname,
  // Django's DRF router URLs end in "/"; without this Next would 308 them to the
  // slash-less form and Django's APPEND_SLASH would bounce straight back.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      // DRF router URLs end in "/". Next strips the trailing slash from `:path*`, and Django's
      // APPEND_SLASH then 301s back to the slashed URL — an infinite loop. Keep the slash explicitly.
      { source: "/api/:path*/", destination: `${API_PROXY_URL}/api/:path*/` },
      { source: "/api/:path*", destination: `${API_PROXY_URL}/api/:path*` },
    ];
  },
};

export default nextConfig;
