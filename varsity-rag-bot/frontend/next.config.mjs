/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  agentRules: false,
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL?.replace(/\/+$/, "");
    if (process.env.NODE_ENV !== "development" || !backendUrl) return [];

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
