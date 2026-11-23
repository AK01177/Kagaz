import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Old URLs from before the admin / org / workspace split keep working.
  async redirects() {
    return [
      { source: "/dashboard", destination: "/workspace/dashboard", permanent: false },
      { source: "/documents", destination: "/workspace/documents", permanent: false },
      { source: "/documents/:id", destination: "/workspace/documents/:id", permanent: false },
      { source: "/review", destination: "/workspace/review", permanent: false },
      { source: "/approvals", destination: "/workspace/approvals", permanent: false },
      { source: "/policies", destination: "/org/policies", permanent: false },
      { source: "/admin/users", destination: "/org/members", permanent: false },
    ];
  },
  async rewrites() {
    const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
