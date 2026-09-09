import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  eslint: {
    // lint is run separately in CI; don't block production builds on lint warnings
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
