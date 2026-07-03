/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Proxy /api/* to the FastAPI backend so the browser never hits a different origin.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
