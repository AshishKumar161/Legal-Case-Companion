import fs from "node:fs";
import type { NextConfig } from "next";

// Patch fs.readlink and fs.readlinkSync on Windows filesystems where non-symlink files return EISDIR instead of EINVAL
const origReadlinkSync = fs.readlinkSync;
(fs as any).readlinkSync = function (...args: [fs.PathLike, (fs.BufferEncodingOption | fs.EncodingOption)?]) {
  try {
    return origReadlinkSync.apply(this, args as never);
  } catch (err: unknown) {
    const error = err as NodeJS.ErrnoException;
    if (error && error.code === "EISDIR") {
      const einval: NodeJS.ErrnoException = new Error(`EINVAL: invalid argument, readlink '${String(args[0])}'`);
      einval.code = "EINVAL";
      throw einval;
    }
    throw err;
  }
};

const origReadlink = fs.readlink;
(fs as any).readlink = function (path: fs.PathLike, options: any, callback?: any) {
  const cb = typeof options === "function" ? options : callback;
  const opt = typeof options === "function" ? {} : options;
  return (origReadlink as any)(path, opt, (err: NodeJS.ErrnoException | null, linkString: string) => {
    if (err && err.code === "EISDIR") {
      const einval: NodeJS.ErrnoException = new Error(`EINVAL: invalid argument, readlink '${String(path)}'`);
      einval.code = "EINVAL";
      return cb ? cb(einval) : undefined;
    }
    return cb ? cb(err, linkString) : undefined;
  });
};

if (fs.promises && fs.promises.readlink) {
  const origPromisesReadlink = fs.promises.readlink;
  (fs.promises as any).readlink = async function (path: fs.PathLike, options?: any) {
    try {
      return await origPromisesReadlink.call(this, path, options);
    } catch (err: unknown) {
      const error = err as NodeJS.ErrnoException;
      if (error && error.code === "EISDIR") {
        const einval: NodeJS.ErrnoException = new Error(`EINVAL: invalid argument, readlink '${String(path)}'`);
        einval.code = "EINVAL";
        throw einval;
      }
      throw err;
    }
  };
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  productionBrowserSourceMaps: false,
  allowedDevOrigins: [
    "*.trycloudflare.com",
    "indiana-controversial-hub-memorabilia.trycloudflare.com",
    "*.loca.lt",
    "*.ngrok-free.app",
    "*.pinggy.link",
  ],
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
              process.env.NODE_ENV === "production"
                ? "script-src 'self' 'unsafe-inline'"
                : "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "img-src 'self' data: blob: https:",
              "font-src 'self' data: https: https://fonts.gstatic.com",
              `connect-src 'self' wss: https:${process.env.NODE_ENV !== "production" ? " http://localhost:8000 http://127.0.0.1:8000 ws://localhost:8000 ws://127.0.0.1:8000" : ""}`,
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
      (process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:8000");
    if (!backendUrl) return [];
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;


