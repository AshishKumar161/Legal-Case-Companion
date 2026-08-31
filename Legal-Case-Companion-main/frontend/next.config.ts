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
  experimental: {
    webpackBuildWorker: false,
  },
  webpack: (config) => {
    config.resolve = config.resolve || {};
    config.resolve.symlinks = false;
    return config;
  },
};

export default nextConfig;
