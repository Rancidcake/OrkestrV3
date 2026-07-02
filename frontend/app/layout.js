import { IBM_Plex_Mono } from "next/font/google"
import "./globals.css"

const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" })

export const metadata = {
  title: "Orkester",
  description: "multimodal agent",
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={mono.variable}>
      <body>{children}</body>
    </html>
  )
}
