import "./env.mjs";
import http from "node:http";
import { readFile, readdir } from "node:fs/promises";
import { resolve, extname } from "node:path";
import searchHandler from "../api/search.js";
import healthHandler from "../api/health.js";
import { accessError, MAX_REQUEST_BYTES } from "./http.mjs";
const production = process.argv.includes("--production");
const vite = production
  ? null
  : await (
      await import("vite")
    ).createServer({ server: { middlewareMode: true }, appType: "spa" });
const staticFiles = new Map();
async function loadStaticFiles(directory, prefix = "") {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) continue;
    const pathname = `${prefix}/${entry.name}`;
    const filename = resolve(directory, entry.name);
    if (entry.isDirectory()) await loadStaticFiles(filename, pathname);
    else if (entry.isFile()) staticFiles.set(pathname, await readFile(filename));
  }
}
if (production) await loadStaticFiles(resolve("dist"));
const port = Number(process.env.PORT || 4199);
const server = http.createServer(async (req, res) => {
  res.status = (n) => {
    res.statusCode = n;
    return res;
  };
  res.json = (data) => {
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(data));
  };
  try {
    const path = req.url.split("?")[0];
    if (path === "/api/health") return healthHandler(req, res);
    if (path === "/api/search") {
      if (req.method !== "POST") return searchHandler(req, res);
      const denied = accessError(req.headers);
      if (denied)
        return res.status(denied.status).json({ error: denied.error });
      let chunks = [],
        size = 0;
      for await (const chunk of req) {
        size += chunk.length;
        if (size > MAX_REQUEST_BYTES)
          return res.status(413).json({ error: "Document is too large." });
        chunks.push(chunk);
      }
      req.body = Buffer.concat(chunks).toString();
      return await searchHandler(req, res);
    }
    if (vite) return vite.middlewares(req, res);
    let file = decodeURIComponent(path);
    if (file.split("/").some((part) => part === ".." || part.startsWith(".")))
      return res.status(403).end();
    if (file.endsWith("/")) file += "index.html";
    if (!staticFiles.has(file)) {
      if (extname(file) || path.startsWith("/api/")) return res.status(404).end();
      file = "/index.html";
    }
    const mime = {
      ".html": "text/html",
      ".js": "text/javascript",
      ".css": "text/css",
      ".svg": "image/svg+xml",
      ".png": "image/png",
      ".zip": "application/zip",
      ".json": "application/json",
    };
    res.setHeader(
      "Content-Type",
      mime[extname(file)] || "application/octet-stream",
    );
    res.end(staticFiles.get(file));
  } catch {
    if (!res.headersSent) res.status(400).json({ error: "Invalid request." });
    else res.end();
  }
});
server.listen(port, "127.0.0.1", () =>
  console.log(`Needle running at http://127.0.0.1:${port}`),
);
async function shutdown() {
  server.close();
  await vite?.close();
  process.exit(0);
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
