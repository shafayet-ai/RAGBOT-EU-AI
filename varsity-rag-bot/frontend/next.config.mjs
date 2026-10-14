/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  agentRules: false,
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_URL?.replace(/\/+$/, "") ??
      (process.env.BACKEND_HOST
        ? `https://${process.env.BACKEND_HOST}`
        : undefined);
    if (!backendUrl) return [];

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
