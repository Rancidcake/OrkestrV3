/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    const raw = process.env.BACKEND_URL ?? "http://localhost:8000"
    const backend = /^https?:\/\//.test(raw) ? raw : `https://${raw}`
    return [
      { source: "/chat",   destination: `${backend}/chat`   },
      { source: "/health", destination: `${backend}/health` },
    ]
  },
}
module.exports = nextConfig
