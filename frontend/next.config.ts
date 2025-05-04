import type { NextConfig } from "next";
import { LOCAL_BACKEND_URL, PRODUCTION_BACKEND_URL, USE_PRODUCTION_BACKEND } from "./src/config/api-config";

// Use the manual toggle to determine which backend to use
const backendUrl = USE_PRODUCTION_BACKEND ? PRODUCTION_BACKEND_URL : LOCAL_BACKEND_URL;

const nextConfig: NextConfig = {
  /* config options here */
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`
      }
    ];
  },
};

export default nextConfig;
