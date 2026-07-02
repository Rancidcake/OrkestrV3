/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://localhost:8000"
    return [
      { source: "/chat",   destination: `${backend}/chat`   },
      { source: "/health", destination: `${backend}/health` },
    ]
  },
}
module.exports = nextConfig
