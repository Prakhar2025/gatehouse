import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  ...(process.env.STATIC_EXPORT ? { output: "export" as const, images: { unoptimized: true } } : {}),
};

export default nextConfig;
