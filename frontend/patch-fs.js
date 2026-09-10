const fs = require("node:fs");

const origReadlinkSync = fs.readlinkSync;
fs.readlinkSync = function (...args) {
  try {
    return origReadlinkSync.apply(this, args);
  } catch (err) {
    if (err && err.code === "EISDIR") {
      const einval = new Error(`EINVAL: invalid argument, readlink '${args[0]}'`);
      einval.code = "EINVAL";
      throw einval;
    }
    throw err;
  }
};

const origReadlink = fs.readlink;
fs.readlink = function (path, options, callback) {
  const cb = typeof options === "function" ? options : callback;
  const opt = typeof options === "function" ? {} : options;
  return origReadlink(path, opt, (err, linkString) => {
    if (err && err.code === "EISDIR") {
      const einval = new Error(`EINVAL: invalid argument, readlink '${path}'`);
      einval.code = "EINVAL";
      return cb(einval);
    }
    return cb(err, linkString);
  });
};

if (fs.promises && fs.promises.readlink) {
  const origPromisesReadlink = fs.promises.readlink;
  fs.promises.readlink = async function (path, options) {
    try {
      return await origPromisesReadlink.call(this, path, options);
    } catch (err) {
      if (err && err.code === "EISDIR") {
        const einval = new Error(`EINVAL: invalid argument, readlink '${path}'`);
        einval.code = "EINVAL";
        throw einval;
      }
      throw err;
    }
  };
}
