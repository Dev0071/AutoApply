import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AutoApply",
  description: "Vision-driven, quality-gated job application agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <Providers>
          <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
            <span className="font-bold text-lg tracking-tight">AutoApply</span>
            <a href="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">Dashboard</a>
            <a href="/profile" className="text-sm text-gray-600 hover:text-gray-900">Profile</a>
          </nav>
          <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
