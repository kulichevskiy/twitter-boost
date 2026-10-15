import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  redirects() {
    // The landing page is the CRM; the course lives under /course.
    return [{ source: "/", destination: "/crm", permanent: false }];
  },
  partialPrefetching: true,
  // Dev server is opened from phones over the tailnet; without this Next
  // blocks HMR for those hosts and the page keeps full-reloading.
  allowedDevOrigins: ["*.ts.net", "100.*.*.*", "localhost", "127.0.0.1", "mini", "macmini", "*.local", "twitter-boost.local"],
  turbopack: {
    // a stray package-lock.json in the home directory otherwise confuses root detection
    root: process.cwd(),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
