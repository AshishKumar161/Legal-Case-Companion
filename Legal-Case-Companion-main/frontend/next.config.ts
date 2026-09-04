import fs from "node:fs";
import type { NextConfig } from "next";

// Patch fs.readlink and fs.readlinkSync on Windows filesystems where non-symlink files return EISDIR instead of EINVAL
const origReadlinkSync = fs.readlinkSync;
(fs as any).readlinkSync = function (...args: any[]) {
  try {
    return origReadlinkSync.apply(this, args as any);
  } catch (err: any) {
    if (err && err.code === "EISDIR") {
      const einval: any = new Error(`EINVAL: invalid argument, readlink '${args[0]}'`);
      einval.code = "EINVAL";
      throw einval;
    }
    throw err;
  }
};

const origReadlink = fs.readlink;
(fs as any).readlink = function (path: any, options: any, callback?: any) {
  const cb = typeof options === "function" ? options : callback;
  const opt = typeof options === "function" ? {} : options;
  return origReadlink(path, opt, (err: any, linkString: any) => {
    if (err && err.code === "EISDIR") {
      const einval: any = new Error(`EINVAL: invalid argument, readlink '${path}'`);
      einval.code = "EINVAL";
      return cb(einval);
    }
    return cb(err, linkString);
  });
};

if (fs.promises && fs.promises.readlink) {
  const origPromisesReadlink = fs.promises.readlink;
  (fs.promises as any).readlink = async function (path: any, options: any) {
    try {
      return await origPromisesReadlink.call(this, path, options);
    } catch (err: any) {
      if (err && err.code === "EISDIR") {
        const einval: any = new Error(`EINVAL: invalid argument, readlink '${path}'`);
        einval.code = "EINVAL";
        throw einval;
      }
      throw err;
    }
  };
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  experimental: {
    webpackBuildWorker: false,
  },
  webpack: (config) => {
    config.resolve = config.resolve || {};
    config.resolve.symlinks = false;
    return config;
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(self), microphone=(self), geolocation=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains; preload",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: https:",
              "font-src 'self' data: https:",
              "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws://localhost:8000 ws://127.0.0.1:8000 wss: https:",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
