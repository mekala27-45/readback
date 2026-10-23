import type { NextConfig } from "next";

// Static export for GitHub Pages, where the site lives under /readback. The same base path is the
// default here, so a plain `npm run build` produces what Pages serves and what Playwright loads.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "/readback";

// The live API. The Pages workflow passes the READBACK_API_URL repository variable, empty until
// someone sets it, so an empty value falls back to the deployed address. The end to end build points
// it at the test server's mock, which refuses HEAD and answers a first 503.
const api = process.env.NEXT_PUBLIC_READBACK_API || "https://readback-mcp.vercel.app";

const config: NextConfig = {
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  env: { NEXT_PUBLIC_BASE_PATH: basePath, NEXT_PUBLIC_READBACK_API: api },
};

export default config;
