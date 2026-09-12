import type { NextConfig } from "next";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

const nextConfig: NextConfig = {
  outputFileTracingRoot: repositoryRoot,
  transpilePackages: ["@aegisos/shared"],
  async rewrites() {
    const apiBaseUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
    return [{ source: "/backend/:path*", destination: `${apiBaseUrl}/:path*` }];
  },
};

export default nextConfig;
