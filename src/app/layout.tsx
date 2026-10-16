import { Suspense } from "react";
import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Inter } from "next/font/google";
import { SiteNav } from "@/components/site-nav";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
});

export const metadata: Metadata = {
  title: { default: "Twitter Boost", template: "%s — Twitter Boost" },
  description: "A personal CRM for your own X (Twitter) account.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Twitter Boost" },
  icons: { apple: "/icons/apple-touch-icon.png", icon: "/icons/icon-192.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <header className="sticky top-0 z-30 border-b bg-background/95 pt-[env(safe-area-inset-top)] backdrop-blur supports-backdrop-filter:bg-background/80">
          <div className="mx-auto flex h-12 max-w-6xl items-center justify-between gap-4 px-4">
            <Link href="/" className="text-sm font-semibold tracking-tight">
              Twitter Boost
            </Link>
            <Suspense fallback={null}>
              <SiteNav />
            </Suspense>
          </div>
        </header>
        <main className="mx-auto w-full flex-1 px-4 pt-4 pb-10">{children}</main>
      </body>
    </html>
  );
}
